"""CU11-C2 – Retreinar o modelo periodicamente, passos 2 a 10 (no serviço `modelo`).

O passo 1 (o agendador e o comando `--retreinar`) registra a execução na fila (TreinamentoService.
registrar_retreinamentos). Aqui:

- passos 2 a 5: os mesmos do C1 (seleção, série só com os dias encerrados, preparação e treino), com a divisão 70/20/10
  recalculada até o último dia encerrado;
- passo 6 (RN26): o modelo novo e o vigente são avaliados no **mesmo** período de teste novo; o vigente com as próprias
  constantes, vocabulário e escala do alvo, aplicados às mesmas variáveis brutas;
- passo 7: o novo substitui o vigente se a mediana do MdAPE por item, nos itens e dias avaliados pelos dois, for
  estritamente menor;
- passo 8 / FA2: o novo vira o vigente, ou fica registrado como descartado, com as métricas e os artefatos;
- passo 9 / FA1: a situação de todos os elegíveis é recalculada com o modelo que ficou vigente; os itens que deixaram
  de ser elegíveis ficam bloqueados;
- passo 10: o resumo vai para a execução e para o log;
- FE1: uma falha nos passos 3 a 8 deixa a execução como FALHA; o vigente e `projecao_item` não mudam.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import delete, insert, tuple_, update
from sqlalchemy.exc import SQLAlchemyError

from src.ml.artefatos import ARQUIVO_AVALIACAO, ARQUIVO_MODELO, ARQUIVO_NORMALIZACAO, ARQUIVO_TREINO, Artefatos
from src.ml.avaliacao import Avaliacao, Comparacao, avaliar, comparar_modelos
from src.ml.configuracao import ConfigModelo
from src.ml.dados import Entrada
from src.ml.dataset import DadosPreparados
from src.ml.preparacao import BasePreparada, VariaveisBrutas, aplicar_versao, mesmas_brutas, preparar_brutas
from src.ml.rede import ResultadoDoTreino
from src.ml.selecao import Selecao
from src.ml.treinamento_inicial import (Contagens, TreinamentoInicial, _Falha, contar, linhas_da_situacao,
                                        situacao_dos_itens)
from src.models.modelo import (DECISAO_MANTIDO, DECISAO_SUBSTITUIDO, ETAPA_BANCO, ETAPA_INTERNA,
                               MOTIVO_DEIXOU_DE_SER_ELEGIVEL, SITUACAO_BLOQUEADA, SITUACAO_LIBERADA, STATUS_SUCESSO,
                               ExecucaoTreinamento, ModeloPreditivo, ProjecaoItem)

logger = logging.getLogger(__name__)

ARQUIVO_AVALIACAO_DO_VIGENTE = "avaliacao_teste_vigente.parquet"


@dataclass
class VersaoVigente:
    """A versão vigente da região, com o que o passo 6 precisa dela."""
    versao: int
    caminho: Path
    corte_validacao: date
    normalizacao: dict[str, Any]
    conjunto_de_treinamento: frozenset[tuple[str, int]]


class Retreinamento(TreinamentoInicial):
    """CU11-C2 passos 2 a 10. Reaproveita as etapas do C1; `treinador` também carrega a rede da versão vigente."""

    rotulo = "CU11-C2"

    def executar(self, id_execucao: int, data_execucao: Optional[date] = None) -> None:
        """`data_execucao`: a data UTC da execução (padrão: a do relógio). RN25: só os dias anteriores a ela entram."""
        contagens = Contagens()
        artefatos = Artefatos(self.pasta, id_execucao)
        ate = data_execucao or self.relogio().date()
        try:
            regiao = self._regiao(id_execucao)
            vigente = self._versao_vigente(regiao)
            entrada, selecao = self._selecionar(id_execucao, regiao, ate, contagens)  # passos 2 e 3
            brutas = self._preparar_brutas(id_execucao, entrada, selecao)  # passo 4 (70/20/10 até o último dia)
            base = self._normalizar(brutas)
            base_vigente = self._base_do_vigente(brutas, vigente, entrada, selecao)
            del entrada, brutas
            selecao.precos = selecao.precos.iloc[0:0]
            dados = DadosPreparados(base)
            dados_vigente = DadosPreparados(base_vigente)
            treino = self._treinar(id_execucao, dados)  # passo 5

            # Passo 6: os dois modelos no mesmo período de teste, cada um com as próprias constantes.
            self._andamento(id_execucao, "Avaliando o modelo novo e o vigente no mesmo período de teste")
            av_novo = self._avaliar(dados, treino.modelo)
            av_vigente = self._avaliar(dados_vigente, self.treinador.carregar(vigente.caminho / ARQUIVO_MODELO))
            comparacao = comparar_modelos(av_novo, av_vigente, self.cfg.metrica_rn10)  # passo 7
            substitui = comparacao.novo_e_melhor

            # Passo 9: a situação de todos os elegíveis, com o modelo que ficou vigente.
            situacao_novo = situacao_dos_itens(selecao, base, av_novo)
            situacao_vigente = situacao_dos_itens(selecao, base, av_vigente, vigente.conjunto_de_treinamento,
                                                  vigente.corte_validacao)
            situacao = situacao_novo if substitui else situacao_vigente
            contagens = contar(situacao, selecao)

            artefatos.iniciar()
            self.treinador.salvar(treino.modelo, artefatos.temporaria / ARQUIVO_MODELO)
            artefatos.gravar_json(ARQUIVO_NORMALIZACAO, base.normalizacao)
            artefatos.gravar_avaliacao(situacao_novo)
            situacao_vigente.to_parquet(artefatos.temporaria / ARQUIVO_AVALIACAO_DO_VIGENTE, index=False)

            self._andamento(id_execucao, "Registrando o retreinamento")
            self._registrar_retreino(id_execucao, regiao, vigente, base, treino, av_novo, comparacao, situacao,
                                     contagens, artefatos, self._avisos(selecao, ate))
        except _Falha as f:
            artefatos.descartar()
            self._falhar(id_execucao, f.etapa, f.erro, contagens)
        except Exception as e:  # FE1: falha interna inesperada nos passos 3 a 8
            logger.exception("CU11-C2: erro inesperado no retreinamento %s.", id_execucao)
            artefatos.descartar()
            self._falhar(id_execucao, ETAPA_INTERNA, repr(e), contagens)

    # ----------------------------------------------------------------------------------------------- passo 6
    def _versao_vigente(self, regiao: str) -> VersaoVigente:
        """Pré-condição do C2: a versão vigente da região, com o normalizacao.json e o conjunto de treinamento dela."""
        try:
            with self.abrir_sessao() as s:
                modelo = s.query(ModeloPreditivo).filter(ModeloPreditivo.regiao == regiao,
                                                         ModeloPreditivo.vigente.is_(True)).one_or_none()
                if modelo is None:
                    raise _Falha(ETAPA_INTERNA, f"Não há modelo vigente na região {regiao} (pré-condição do CU11-C2).")
                versao, caminho, corte = modelo.versao, Path(modelo.caminho_artefatos), modelo.corte_validacao
        except SQLAlchemyError as e:
            raise _Falha(ETAPA_BANCO, f"Falha ao ler a versão vigente: {e}") from e
        normalizacao = json.loads((caminho / ARQUIVO_NORMALIZACAO).read_text(encoding="utf-8"))
        conjunto: frozenset[tuple[str, int]] = frozenset()
        if (caminho / ARQUIVO_AVALIACAO).exists():
            itens = pd.read_parquet(caminho / ARQUIVO_AVALIACAO, columns=["serie", "item_id", "integra_treino"])
            itens = itens[itens["integra_treino"].astype(bool)]
            conjunto = frozenset(zip(itens["serie"].astype(str).tolist(), itens["item_id"].astype(int).tolist()))
        return VersaoVigente(versao, caminho, corte, normalizacao, conjunto)

    def _base_do_vigente(self, brutas: VariaveisBrutas, vigente: VersaoVigente, entrada: Entrada,
                         selecao: Selecao) -> BasePreparada:
        """As variáveis brutas são as mesmas quando a configuração que as define não mudou (a base é lida e higienizada
        uma vez só); se mudou, são recalculadas com a configuração da versão vigente, nos mesmos cortes novos."""
        cfg_vigente = ConfigModelo.de_dict(vigente.normalizacao["config"])
        if not mesmas_brutas(brutas.cfg, cfg_vigente):
            logger.warning("CU11-C2: a configuração das variáveis brutas mudou desde a versão %s; recalculando-as para "
                           "avaliá-la.", vigente.versao)
            cortes = {k: brutas.cortes[k].date().isoformat() for k in ("corte_validacao", "corte_teste")}
            brutas = preparar_brutas(entrada, selecao.precos, cfg_vigente, selecao.fora_do_treino,
                                     cortes["corte_validacao"], cortes["corte_teste"])
        return aplicar_versao(brutas, vigente.normalizacao)

    # ------------------------------------------------------------------------------------------- passos 8 a 10
    def _registrar_retreino(self, id_execucao: int, regiao: str, vigente: VersaoVigente, base: BasePreparada,
                            treino: ResultadoDoTreino, av_novo: Avaliacao, comparacao: Comparacao,
                            situacao: pd.DataFrame, contagens: Contagens, artefatos: Artefatos,
                            avisos: Optional[str]) -> None:
        """Passo 8 (ou FA2), passo 9 (com o FA1) e passo 10, numa só transação: se ela falhar (FE1), o vigente e a
        situação dos itens ficam como estavam."""
        substitui = comparacao.novo_e_melhor
        with self.abrir_sessao() as s:
            try:
                agora = self.relogio()
                if substitui:
                    s.execute(update(ModeloPreditivo).where(ModeloPreditivo.versao == vigente.versao)
                              .values(vigente=False, substituido_em=agora))
                novo = self._novo_modelo(id_execucao, regiao, base, treino, av_novo, contagens, agora,
                                         vigente=substitui)
                s.add(novo)
                s.flush()
                versao_vigente = novo.versao if substitui else vigente.versao
                artefatos.gravar_json(ARQUIVO_TREINO, {
                    **self._info_do_treino(id_execucao, novo.versao, regiao, treino, av_novo, contagens, base),
                    "comparacao_com_o_vigente": {**comparacao.como_dict(), "versao_vigente": vigente.versao,
                                                 "decisao": DECISAO_SUBSTITUIDO if substitui else DECISAO_MANTIDO},
                })
                novo.caminho_artefatos = artefatos.publicar(novo.versao).as_posix()
                deixaram, liberados_deixaram = self._gravar_situacao_do_retreino(s, regiao, versao_vigente, situacao,
                                                                                 agora)

                execucao = s.get(ExecucaoTreinamento, id_execucao)
                execucao.status = STATUS_SUCESSO
                execucao.concluido_em = agora
                execucao.versao = novo.versao
                execucao.versao_anterior = vigente.versao
                execucao.decisao = DECISAO_SUBSTITUIDO if substitui else DECISAO_MANTIDO
                execucao.mdape_novo = comparacao.mediana_novo
                execucao.mdape_vigente = comparacao.mediana_vigente
                execucao.itens_comparados = comparacao.itens_comparados
                execucao.deixaram_de_ser_elegiveis = deixaram
                execucao.liberados_que_deixaram_de_ser_elegiveis = liberados_deixaram
                execucao.andamento = "Concluído"
                execucao.avisos = avisos
                for campo, valor in contagens.como_dict().items():
                    setattr(execucao, campo, valor)
                versao_nova = novo.versao
                s.commit()
            except SQLAlchemyError as e:
                s.rollback()
                raise _Falha(ETAPA_BANCO, f"Falha ao registrar o retreinamento: {e}") from e
            artefatos.confirmar()  # FA2 também mantém os artefatos do modelo descartado
        logger.info(
            "CU11-C2: retreinamento %s em %s concluído. Vigente anterior: v%s; novo: v%s; decisão: %s (mediana do %s por "
            "item em %d itens comparados: novo %s, vigente %s). Deixaram de ser elegíveis: %d (%d liberados). "
            "Resumo: %s.", id_execucao, regiao, vigente.versao, versao_nova,
            DECISAO_SUBSTITUIDO if substitui else DECISAO_MANTIDO, comparacao.metrica.upper(),
            comparacao.itens_comparados, _pct(comparacao.mediana_novo), _pct(comparacao.mediana_vigente), deixaram,
            liberados_deixaram, contagens.como_dict())

    def _gravar_situacao_do_retreino(self, s: Any, regiao: str, versao_vigente: int, situacao: pd.DataFrame,
                                     agora: Any) -> tuple[int, int]:
        """Passo 9: a situação de cada elegível é substituída pela nova. FA1: os itens da região que não são mais
        elegíveis ficam bloqueados ("deixou de ser elegível"), com as métricas da última avaliação. Devolve quantos
        deixaram de ser elegíveis nesta execução e quantos deles estavam liberados."""
        existentes = {(str(r.serie), int(r.item_id)): r.situacao for r in
                      s.query(ProjecaoItem.serie, ProjecaoItem.item_id, ProjecaoItem.situacao, ProjecaoItem.motivo)
                      .filter(ProjecaoItem.regiao == regiao)
                      if not (r.situacao == SITUACAO_BLOQUEADA and r.motivo == MOTIVO_DEIXOU_DE_SER_ELEGIVEL)}
        elegiveis = set(zip(situacao["serie"].astype(str).tolist(), situacao["item_id"].astype(int).tolist()))
        deixaram = [chave for chave in existentes if chave not in elegiveis]
        liberados_deixaram = sum(1 for chave in deixaram if existentes[chave] == SITUACAO_LIBERADA)

        chaves = list(elegiveis)
        for inicio in range(0, len(chaves), 5000):
            s.execute(delete(ProjecaoItem).where(ProjecaoItem.regiao == regiao, tuple_(
                ProjecaoItem.serie, ProjecaoItem.item_id).in_(chaves[inicio:inicio + 5000])))
        linhas = linhas_da_situacao(situacao, regiao, versao_vigente, agora)
        if linhas:
            s.execute(insert(ProjecaoItem), linhas)
        for inicio in range(0, len(deixaram), 5000):
            s.execute(update(ProjecaoItem).where(ProjecaoItem.regiao == regiao, tuple_(
                ProjecaoItem.serie, ProjecaoItem.item_id).in_(deixaram[inicio:inicio + 5000]))
                .values(situacao=SITUACAO_BLOQUEADA, motivo=MOTIVO_DEIXOU_DE_SER_ELEGIVEL, atualizado_em=agora))
        return len(deixaram), liberados_deixaram


def _pct(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.2%}"
