"""CU11-C3 – Consolidar predições diárias (no serviço `modelo`).

Para cada região com modelo vigente:

- passo 2: espera a importação diária do worker (CU10-C1); se ela falhou ou não rodou, segue com um aviso (FA2);
- para cada dia ainda não consolidado (FE1), na ordem, numa só transação:
  - passos 3 a 6 (RN13) e FA2: o valor real e o erro de cada predição do dia ("N/D" sem valor real);
  - FA1: sem predição para o dia, segue para o passo 7;
  - FA3 (RN13): o bloqueio por degradação;
  - passo 7, só no dia de referência mais recente (sem previsões retroativas): as previsões dos próximos 7 dias dos
    itens liberados, com o modelo vigente (src/ml/previsao.py);
  - o registro do dia em `consolidacao_diaria`;
- FE1: a falha desfaz o dia, vai para o log e para o registro, e o próximo disparo reprocessa os dias que faltam;
- passo 8 e FA4: a conclusão vai para o log; se os bloqueados por degradação no dia passarem de MODELO_DEGRADACAO_GERAL
  (20%) dos liberados no início do dia, o retreinamento (C2) é registrado pelo mesmo caminho do agendador.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Optional

from sqlalchemy import insert, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.ml.configuracao import ConfigModelo
from src.ml.previsao import VersaoParaPrever, prever_dia
from src.ml.rede import Treinador
from src.models.modelo import STATUS_FALHA, STATUS_SUCESSO, ConsolidacaoDiaria, ModeloPreditivo, PredicaoDiaria
from src.services import security
from src.services.consolidacao_service import ConsolidacaoService, EstadoDaImportacao
from src.services.treinamento_service import TRAVA_DA_SITUACAO_DOS_ITENS, TreinamentoService

logger = logging.getLogger(__name__)

TRAVA_DA_CONSOLIDACAO = "hashtext('consolidacao_diaria')"


@dataclass
class ResumoDoDia:
    regiao: str
    dia: date
    status: str
    predicoes_do_dia: int = 0
    predicoes_preenchidas: int = 0
    predicoes_nd: int = 0
    itens_liberados_no_inicio: int = 0
    itens_bloqueados_degradacao: int = 0
    previsoes_gravadas: int = 0
    itens_sem_janela: Optional[int] = None
    retreinamento_antecipado: bool = False
    erro: Optional[str] = None


@dataclass
class ResumoDaConsolidacao:
    """Passo 8: a conclusão da consolidação, para o log (e para o comando `--consolidar`)."""
    importacao: EstadoDaImportacao
    dias: list[ResumoDoDia] = field(default_factory=list)


class Consolidacao:
    """CU11-C3. `treinador` carrega e roda a rede da versão vigente (TreinadorKeras); os testes injetam um falso."""

    def __init__(self, engine: Engine, cfg: ConfigModelo, treinador: Optional[Treinador] = None,
                 relogio: Callable[[], Any] = security.agora, dormir: Callable[[float], Any] = time.sleep) -> None:
        self.engine = engine
        self.abrir_sessao = sessionmaker(bind=engine)
        self.cfg = cfg
        if treinador is None:
            from src.ml.rede import TreinadorKeras
            treinador = TreinadorKeras()
        self.treinador = treinador
        self.relogio = relogio
        self.dormir = dormir

    def executar(self, data_execucao: Optional[date] = None) -> Optional[ResumoDaConsolidacao]:
        """Consolida o último dia encerrado (D, a véspera da data UTC da execução) e os dias que ficaram para trás.
        Devolve None se outra consolidação já estiver rodando (a agendada e a do comando nunca rodam juntas)."""
        hoje = data_execucao or self.relogio().date()
        dia_de_referencia = hoje - timedelta(days=1)
        with self.engine.connect() as trava:
            obtida = trava.execute(text(f"SELECT pg_try_advisory_lock({TRAVA_DA_CONSOLIDACAO})")).scalar()
            trava.commit()  # a trava é da sessão: não precisa de uma transação aberta durante a consolidação
            if not obtida:
                logger.info("CU11-C3: já existe uma consolidação em andamento; esta não começa.")
                return None
            try:
                with self.abrir_sessao() as s:
                    importacao = ConsolidacaoService(s, self.cfg, self.relogio).aguardar_importacao_diaria(
                        desligada=os.getenv("HISTORICO_IMPORTACAO_DIARIA_CRON", "").strip().lower() == "off",
                        dormir=self.dormir)
                    regioes = sorted(r for (r,) in s.query(ModeloPreditivo.regiao)
                                     .filter(ModeloPreditivo.vigente.is_(True)))
                if importacao.aviso:
                    logger.warning("CU11-C3: %s.", importacao.aviso)
                resumo = ResumoDaConsolidacao(importacao)
                for regiao in regioes:
                    resumo.dias += self._consolidar_regiao(regiao, dia_de_referencia, importacao)
            finally:
                trava.execute(text(f"SELECT pg_advisory_unlock({TRAVA_DA_CONSOLIDACAO})"))
                trava.commit()
        for dia in resumo.dias:  # passo 8
            logger.info("CU11-C3: consolidação de %s em %s: %s.", dia.dia, dia.regiao, dia)
        return resumo

    # ------------------------------------------------------------------------------------------------ região
    def _consolidar_regiao(self, regiao: str, dia_de_referencia: date,
                           importacao: EstadoDaImportacao) -> list[ResumoDoDia]:
        with self.abrir_sessao() as s:
            pendentes = ConsolidacaoService(s, self.cfg, self.relogio).dias_pendentes(regiao, dia_de_referencia)
        resumos: list[ResumoDoDia] = []
        antecipou = False
        for dia in pendentes:
            try:
                resumo = self._consolidar_dia(regiao, dia, dia == dia_de_referencia, importacao)
            except Exception as e:  # FE1: a transação do dia foi desfeita; o próximo disparo o reprocessa
                logger.exception("CU11-C3-FE1: a consolidação de %s em %s foi desfeita.", dia, regiao)
                resumos.append(self._registrar_falha(regiao, dia, importacao, e))
                break
            if not antecipou and self._degradacao_generalizada(resumo):
                antecipou = self._antecipar_retreinamento(regiao, dia, resumo)
            resumos.append(resumo)
        return resumos

    def _consolidar_dia(self, regiao: str, dia: date, gerar_previsoes: bool,
                        importacao: EstadoDaImportacao) -> ResumoDoDia:
        """Um dia, numa só transação: passos 3 a 6, FA1, FA2, FA3, o passo 7 (só no dia mais recente) e o registro."""
        with self.abrir_sessao() as s:
            iniciado_em = self.relogio()
            s.execute(text(TRAVA_DA_SITUACAO_DOS_ITENS))
            servico = ConsolidacaoService(s, self.cfg, self.relogio)
            resumo = ResumoDoDia(regiao, dia, STATUS_SUCESSO)
            resumo.itens_liberados_no_inicio = servico.contar_liberados(regiao)
            resumo.predicoes_do_dia, resumo.predicoes_preenchidas, resumo.predicoes_nd = \
                servico.preencher_valores_reais(regiao, dia)
            if resumo.predicoes_do_dia:  # FA1: sem predição para o dia, segue para o passo 7
                resumo.itens_bloqueados_degradacao = len(servico.aplicar_degradacao(regiao, dia))

            vigente = s.query(ModeloPreditivo).filter(ModeloPreditivo.regiao == regiao,
                                                      ModeloPreditivo.vigente.is_(True)).one()
            if gerar_previsoes:
                previsoes = prever_dia(self.engine, self.cfg, regiao,
                                       VersaoParaPrever.da_pasta(vigente.versao, vigente.caminho_artefatos),
                                       servico.liberados(regiao), dia, self.treinador, self.relogio())
                if previsoes.linhas:
                    s.execute(insert(PredicaoDiaria), previsoes.linhas)
                resumo.previsoes_gravadas = len(previsoes.linhas)
                resumo.itens_sem_janela = previsoes.itens_sem_janela
            self._gravar_resumo(servico, resumo, importacao, vigente.versao, iniciado_em)
            s.commit()
        return resumo

    def _gravar_resumo(self, servico: ConsolidacaoService, resumo: ResumoDoDia, importacao: EstadoDaImportacao,
                       versao: Optional[int], iniciado_em: Any) -> None:
        servico.registrar(
            resumo.regiao, resumo.dia, resumo.status, iniciado_em=iniciado_em, versao=versao,
            importacao_diaria=importacao.situacao, avisos=importacao.aviso, erro=resumo.erro,
            predicoes_do_dia=resumo.predicoes_do_dia, predicoes_preenchidas=resumo.predicoes_preenchidas,
            predicoes_nd=resumo.predicoes_nd, itens_liberados_no_inicio=resumo.itens_liberados_no_inicio,
            itens_bloqueados_degradacao=resumo.itens_bloqueados_degradacao,
            previsoes_gravadas=resumo.previsoes_gravadas, itens_sem_janela=resumo.itens_sem_janela,
        )

    def _registrar_falha(self, regiao: str, dia: date, importacao: EstadoDaImportacao, e: Exception) -> ResumoDoDia:
        """FE1: o dia fica registrado como `FALHA`, com o erro, numa transação à parte (a do dia foi desfeita)."""
        resumo = ResumoDoDia(regiao, dia, STATUS_FALHA, erro=repr(e))
        try:
            with self.abrir_sessao() as s:
                self._gravar_resumo(ConsolidacaoService(s, self.cfg, self.relogio), resumo, importacao, None,
                                    self.relogio())
                s.commit()
        except Exception:
            logger.exception("CU11-C3: não foi possível registrar a falha da consolidação de %s em %s.", dia, regiao)
        return resumo

    # --------------------------------------------------------------------------------------------------- FA4
    def _degradacao_generalizada(self, resumo: ResumoDoDia) -> bool:
        """FA4: os bloqueados por degradação no dia passam de MODELO_DEGRADACAO_GERAL dos liberados no início do dia."""
        return resumo.itens_liberados_no_inicio > 0 and \
            resumo.itens_bloqueados_degradacao > self.cfg.degradacao_geral * resumo.itens_liberados_no_inicio

    def _antecipar_retreinamento(self, regiao: str, dia: date, resumo: ResumoDoDia) -> bool:
        """FA4: o retreinamento (C2) é registrado pelo mesmo caminho do agendador, que não duplica uma execução que já
        está na fila ou rodando."""
        logger.warning("CU11-C3-FA4: %d de %d itens liberados de %s bloqueados por degradação em %s: antecipando o "
                       "retreinamento.", resumo.itens_bloqueados_degradacao, resumo.itens_liberados_no_inicio, regiao,
                       dia)
        try:
            with self.abrir_sessao() as s:
                [registro] = TreinamentoService(s, self.relogio).registrar_retreinamentos([regiao])
                if registro.id_execucao is not None:
                    s.execute(update(ConsolidacaoDiaria)
                              .where(ConsolidacaoDiaria.regiao == regiao, ConsolidacaoDiaria.dia == dia)
                              .values(retreinamento_antecipado=True, id_execucao_retreinamento=registro.id_execucao))
                    s.commit()
                    resumo.retreinamento_antecipado = True
                return True
        except Exception:
            logger.exception("CU11-C3-FA4: não foi possível registrar o retreinamento antecipado de %s.", regiao)
            return False
