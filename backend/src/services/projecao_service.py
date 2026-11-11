"""CU05 – Consultar Previsão Preditiva, Cenário 01 (passos 2 e 3): a situação da projeção do item e as predições a exibir.

A API não carrega a rede: só lê as predições que o CU11-C3 grava todo dia em `predicao_diaria` (a inferência, em lote) e a
situação de cada item em `projecao_item` (a avaliação do CU11, RN10 e RN13). Os textos vão com o texto exato do cenário.
"""
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

from sqlalchemy.orm import Session

from src.ml.configuracao import ConfigModelo
from src.models.api_models import AvisoDaProjecao, PredicaoDoDia, ProjecaoDoItemResponse, SituacaoDaProjecao
from src.models.modelo import (MOTIVO_ACIMA_DO_LIMIAR, MOTIVO_AVALIACAO_INSUFICIENTE, MOTIVO_DEGRADACAO,
                               MOTIVO_DEIXOU_DE_SER_ELEGIVEL, MOTIVO_NAO_SUPERA_INGENUO, SITUACAO_IGNORADA,
                               SITUACAO_LIBERADA, ProjecaoItem)
from src.repositories.projecao_repository import DadosDaSerie, ProjecaoRepository
from src.services import mensagens, security

logger = logging.getLogger(__name__)

# CU05-C1-FA7: o dia de referência da projeção pode ficar até este número de dias atrás do último dia encerrado.
PROJECAO_DESATUALIZADA_DIAS = int(os.getenv("PROJECAO_DESATUALIZADA_DIAS", "2"))

_MOTIVO_PARA_SITUACAO: dict[str, tuple[SituacaoDaProjecao, str]] = {
    MOTIVO_ACIMA_DO_LIMIAR: ("REPROVADA", mensagens.PROJECAO_REPROVADA),  # FA3 (RN10)
    MOTIVO_NAO_SUPERA_INGENUO: ("REPROVADA", mensagens.PROJECAO_REPROVADA),  # FA3 (RN10)
    MOTIVO_AVALIACAO_INSUFICIENTE: ("EM_AVALIACAO", mensagens.PROJECAO_EM_AVALIACAO),  # FA4 (RN10)
    MOTIVO_DEGRADACAO: ("SUSPENSA", mensagens.PROJECAO_SUSPENSA),  # FA5 (RN13)
}


def _indisponivel(situacao: SituacaoDaProjecao, mensagem: str) -> ProjecaoDoItemResponse:
    return ProjecaoDoItemResponse(situacao=situacao, mensagem=mensagem)


def _data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def atende_rn02(dados: DadosDaSerie, cfg: ConfigModelo) -> bool:
    """RN02, como em `criterios_dos_itens` (src/ml/selecao.py): a quantidade média dos últimos `liquidez_dias` dias da
    base é maior que `liquidez_min_quantidade`."""
    return dados.quantidade_media_recente is not None and dados.quantidade_media_recente > cfg.liquidez_min_quantidade


def atende_rn27(dados: DadosDaSerie, cfg: ConfigModelo) -> bool:
    """RN27, como em `criterios_dos_itens`: ao menos `historico_minimo_dias` dias do primeiro registro diário do item até
    o último dia da base."""
    return (dados.ultimo_dia_da_base is not None and dados.primeiro_registro is not None
            and (dados.ultimo_dia_da_base - dados.primeiro_registro).days + 1 >= cfg.historico_minimo_dias)


def criterio_nao_atendido(dados: DadosDaSerie, cfg: ConfigModelo) -> Optional[str]:
    """CU05-C1-FA2: a mensagem do critério de elegibilidade não atendido. Se os dois falham, vale a da RN02. None: o item
    atende aos dois."""
    if not atende_rn02(dados, cfg):
        return mensagens.PROJECAO_POUCA_QUANTIDADE
    if not atende_rn27(dados, cfg):
        return mensagens.PROJECAO_HISTORICO_INSUFICIENTE
    return None


class ProjecaoService:
    def __init__(self, session: Session, relogio: Callable[[], datetime] = security.agora,
                 cfg: Optional[ConfigModelo] = None, desatualizada_dias: int = PROJECAO_DESATUALIZADA_DIAS):
        self.repositorio = ProjecaoRepository(session)
        self.relogio = relogio
        self.cfg = cfg or ConfigModelo.do_ambiente()
        self.desatualizada_dias = desatualizada_dias

    def projecao_do_item(self, item_id: int, regiao: str = "US") -> ProjecaoDoItemResponse:
        """CU05-C1 passos 2 e 3 (RN02, RN10, RN13, RN27): a situação da projeção do item, ou as predições a exibir."""
        hoje = self.relogio().astimezone(timezone.utc).date()
        vigente = self.repositorio.vigente(regiao)
        if vigente is None:
            return _indisponivel("MODELO_NAO_TREINADO", mensagens.PROJECAO_MODELO_NAO_TREINADO)  # FA1

        projecao = self._serie_exibida(self.repositorio.projecoes_do_item(item_id, regiao), item_id, regiao, hoje)
        if projecao is None or projecao.motivo == MOTIVO_DEIXOU_DE_SER_ELEGIVEL:
            return self._elegibilidade_atual(item_id, regiao, hoje, projecao)
        if projecao.situacao == SITUACAO_IGNORADA:  # CU11-C1-FA3: série curta demais para a janela do modelo
            return _indisponivel("NAO_ELEGIVEL", mensagens.PROJECAO_HISTORICO_INSUFICIENTE)  # FA2 (RN27)
        if projecao.situacao != SITUACAO_LIBERADA:
            situacao, mensagem = _MOTIVO_PARA_SITUACAO.get(projecao.motivo or "", ("REPROVADA", mensagens.PROJECAO_REPROVADA))
            return _indisponivel(situacao, mensagem)  # FA3 a FA5
        return self._predicoes(projecao, vigente.versao, hoje)

    def _serie_exibida(self, projecoes: Sequence[ProjecaoItem], item_id: int, regiao: str,
                       hoje: date) -> Optional[ProjecaoItem]:
        """Série do item: a com projeção liberada; havendo mais de uma candidata, a de maior quantidade média ofertada."""
        if len(projecoes) <= 1:
            return projecoes[0] if projecoes else None
        liberadas = [p for p in projecoes if p.situacao == SITUACAO_LIBERADA] or list(projecoes)
        if len(liberadas) == 1:
            return liberadas[0]
        quantidade = {p.serie: self._dados(p.serie, item_id, regiao, hoje).quantidade_media_recente or 0.0
                      for p in liberadas}
        return max(liberadas, key=lambda p: (quantidade[p.serie], p.serie))

    def _dados(self, serie: str, item_id: int, regiao: str, hoje: date) -> DadosDaSerie:
        return self.repositorio.dados_da_serie(serie, item_id, regiao, hoje, self.cfg.liquidez_dias)

    def _elegibilidade_atual(self, item_id: int, regiao: str, hoje: date,
                             projecao: Optional[ProjecaoItem]) -> ProjecaoDoItemResponse:
        """CU05-C1-FA2: o item não foi avaliado pelo CU11 (ou deixou de ser elegível): os critérios são recalculados agora,
        só para ele. Se ele atende aos dois, ficou elegível depois do último treino e espera a próxima avaliação (FA4)."""
        series = [projecao.serie] if projecao is not None else self.repositorio.series_do_item(item_id, regiao, hoje)
        dados = [self._dados(serie, item_id, regiao, hoje) for serie in series]
        if not dados:
            return _indisponivel("NAO_ELEGIVEL", mensagens.PROJECAO_POUCA_QUANTIDADE)  # sem série diária: RN02 e RN27
        if any(criterio_nao_atendido(d, self.cfg) is None for d in dados):
            return _indisponivel("EM_AVALIACAO", mensagens.PROJECAO_EM_AVALIACAO)  # FA4 (decisão do autor, 11/11/2026)
        principal = max(dados, key=lambda d: (d.quantidade_media_recente or 0.0, d.serie))
        return _indisponivel("NAO_ELEGIVEL", criterio_nao_atendido(principal, self.cfg) or mensagens.PROJECAO_POUCA_QUANTIDADE)

    def _predicoes(self, projecao: ProjecaoItem, versao: int, hoje: date) -> ProjecaoDoItemResponse:
        """CU05-C1 passo 3: as predições mais recentes da versão vigente, só os dias a partir de hoje (FA6, FA7)."""
        predicoes = self.repositorio.predicoes_mais_recentes(projecao.serie, projecao.item_id, versao)
        exibidas = [p for p in predicoes if p.data_prevista >= hoje]
        if not exibidas:
            return _indisponivel("NAO_DISPONIVEL", mensagens.PROJECAO_NAO_DISPONIVEL)  # FA6
        referencia = exibidas[0].data_previsao
        base = self.repositorio.preco_diario(projecao.serie, projecao.item_id, referencia)
        if not base:
            logger.warning("CU05: sem o preço diário de %s do item %s (série %s); projeção omitida.",
                           referencia, projecao.item_id, projecao.serie)
            return _indisponivel("NAO_DISPONIVEL", mensagens.PROJECAO_NAO_DISPONIVEL)  # FA6

        ultimo_dia_encerrado = hoje - timedelta(days=1)
        desatualizada = (ultimo_dia_encerrado - referencia).days > self.desatualizada_dias  # FA7
        erro = None if projecao.mdape is None else math.floor(projecao.mdape * 100 + 0.5)
        gerada_em = min(p.criado_em for p in predicoes).astimezone(timezone.utc).date()
        avisos = [AvisoDaProjecao(codigo="ORIGEM", texto=mensagens.PROJECAO_ORIGEM.format(
            gerada_em=_data(gerada_em), referencia=_data(referencia)))]
        if erro is not None:
            avisos.append(AvisoDaProjecao(codigo="ERRO_TIPICO", texto=mensagens.PROJECAO_ERRO_TIPICO.format(pct=erro)))
        avisos.append(AvisoDaProjecao(codigo="ESTIMATIVA", texto=mensagens.PROJECAO_ESTIMATIVA))
        if desatualizada:
            avisos.append(AvisoDaProjecao(codigo="DESATUALIZADA", texto=mensagens.PROJECAO_DESATUALIZADA))
        return ProjecaoDoItemResponse(
            situacao="DISPONIVEL", data_referencia=referencia, preco_referencia=base, erro_tipico_pct=erro,
            desatualizada=desatualizada, avisos=avisos,
            predicoes=[PredicaoDoDia(data_prevista=p.data_prevista, preco_previsto=int(p.preco_previsto),
                                     variacao_pct=round((int(p.preco_previsto) - base) / base * 100, 1))
                       for p in exibidas],
        )
