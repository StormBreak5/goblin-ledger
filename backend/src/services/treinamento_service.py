"""CU11-C1 – Executar treinamento inicial: o pedido do Admin e a fila de execuções.

A API (que não tem TensorFlow) só registra o pedido; o serviço `modelo` o retira da fila (`pegar_proximo`) e executa o
pipeline (src/ml/treinamento_inicial.py). Este módulo não importa pandas nem TensorFlow.
"""
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import func, text, update
from sqlalchemy.orm import Session

from src.models.modelo import (DISPARO_ADMIN, ETAPA_BANCO, ETAPA_INTERNA, ETAPA_SELECAO, ETAPA_TREINO,
                               STATUS_AGUARDANDO, STATUS_EM_ANDAMENTO, STATUS_EXECUTANDO, STATUS_FALHA, TIPO_INICIAL,
                               ExecucaoTreinamento, ModeloPreditivo)
from src.services import mensagens, security, validacao
from src.services.erros import RegiaoInvalidaError, TreinamentoEmAndamentoError, TreinamentoNaoEncontradoError

logger = logging.getLogger(__name__)

# CU11-C1-FA2: um treinamento "em andamento" além deste prazo (o processo parou no meio) deixa de bloquear os novos,
# como na importação do CU10-C1. O treinamento completo leva de 20 a 35 minutos (relatório da etapa 2e).
TEMPO_MAXIMO_DO_TREINAMENTO = timedelta(hours=float(os.getenv("MODELO_TEMPO_MAXIMO_HORAS", "6")))
TRAVA_DO_TREINAMENTO = "SELECT pg_advisory_xact_lock(hashtext('treinamento_modelo'))"

MENSAGEM_DA_FALHA = {
    ETAPA_SELECAO: mensagens.NENHUM_ITEM_APTO,  # CU11-C1-FA1
    ETAPA_TREINO: mensagens.FALHA_NO_TREINAMENTO_DO_MODELO,  # CU11-C1-FE1
    ETAPA_BANCO: mensagens.FALHA_NO_TREINAMENTO,  # CU11-C1-FE2
    ETAPA_INTERNA: mensagens.FALHA_NO_TREINAMENTO,
}


@dataclass
class ResumoDoModelo:
    """A versão registrada no passo 11, com as métricas no período de teste."""
    versao: int
    treinado_em: datetime
    vigente: bool
    data_inicio: date
    corte_validacao: date
    corte_teste: date
    data_fim: date
    itens_avaliados: int
    amostras_treino: int
    amostras_validacao: int
    amostras_teste: int
    epocas: int
    melhor_epoca: int
    segundos_por_epoca: float
    duracao_segundos: float
    mediana_mdape: Optional[float]
    mediana_mdape_ingenuo: Optional[float]
    mediana_mape: Optional[float]
    mediana_mape_ingenuo: Optional[float]
    itens_supera_ingenuo: Optional[int]


@dataclass
class ResumoDoTreinamento:
    """CU11-C1 passo 12: o resumo do treinamento (ou o andamento, enquanto ele roda), com a mensagem do fluxo
    alternativo ou de exceção quando falhou."""
    id_execucao: int
    tipo: str
    disparo: str
    regiao: str
    status: str
    solicitado_em: datetime
    iniciado_em: Optional[datetime]
    concluido_em: Optional[datetime]
    andamento: Optional[str]
    itens_elegiveis: Optional[int]
    itens_treino: Optional[int]
    itens_liberados: Optional[int]
    itens_bloqueados: Optional[int]
    bloqueados_acima_do_limiar: Optional[int]
    bloqueados_nao_supera_ingenuo: Optional[int]
    bloqueados_avaliacao_insuficiente: Optional[int]
    itens_ignorados: Optional[int]
    liberados_fora_do_treino: Optional[int]
    avisos: Optional[str]
    etapa_da_falha: Optional[str]
    mensagem: Optional[str]
    erro: Optional[str]
    modelo: Optional[ResumoDoModelo]


class TreinamentoService:
    """CU11-C1 passos 1 e 12 e fluxo alternativo 2."""

    def __init__(self, session: Session, relogio: Callable[[], datetime] = security.agora):
        self.session = session
        self.relogio = relogio

    def validar_regiao(self, regiao: str) -> str:
        """CU11-C1 passo 1 (RN11): a região é US ou EU. O cenário não define a mensagem; vale a do CU09-C4."""
        normalizada = validacao.normalizar_regiao(regiao)
        if normalizada is None:
            raise RegiaoInvalidaError()
        return normalizada

    def _encerrar_interrompidos(self, agora: datetime) -> None:
        """Um treinamento parado há mais que o prazo (o processo caiu) é encerrado como falha e deixa de bloquear."""
        inicio = func.coalesce(ExecucaoTreinamento.iniciado_em, ExecucaoTreinamento.solicitado_em)
        self.session.execute(
            update(ExecucaoTreinamento)
            .where(ExecucaoTreinamento.status.in_(STATUS_EM_ANDAMENTO), inicio < agora - TEMPO_MAXIMO_DO_TREINAMENTO)
            .values(status=STATUS_FALHA, concluido_em=agora, etapa_da_falha=ETAPA_INTERNA,
                    erro="Treinamento interrompido: o processo parou antes de concluí-lo.")
        )

    def registrar_pedido(self, regiao: str, tipo: str = TIPO_INICIAL, disparo: str = DISPARO_ADMIN) -> int:
        """CU11-C1 passo 1 e FA2: registra o pedido na fila. A checagem e o registro são atômicos (trava do PostgreSQL),
        então dois pedidos simultâneos nunca entram juntos."""
        agora = self.relogio()
        self.session.execute(text(TRAVA_DO_TREINAMENTO))
        self._encerrar_interrompidos(agora)
        em_andamento = (
            self.session.query(ExecucaoTreinamento.id)
            .filter(ExecucaoTreinamento.status.in_(STATUS_EM_ANDAMENTO)).first()
        )
        if em_andamento is not None:
            self.session.rollback()
            raise TreinamentoEmAndamentoError()
        execucao = ExecucaoTreinamento(tipo=tipo, disparo=disparo, regiao=regiao, status=STATUS_AGUARDANDO,
                                       solicitado_em=agora, andamento="Aguardando o serviço de treinamento")
        self.session.add(execucao)
        self.session.commit()
        logger.info("CU11-C1: treinamento %s (%s, %s) registrado na fila.", execucao.id, tipo, regiao)
        return execucao.id

    def pegar_proximo(self) -> Optional[int]:
        """Serviço `modelo`: retira o pedido mais antigo da fila e o marca como em execução. Nada a fazer se a fila
        estiver vazia ou se outro treinamento já estiver rodando."""
        agora = self.relogio()
        self.session.execute(text(TRAVA_DO_TREINAMENTO))
        self._encerrar_interrompidos(agora)
        rodando = (
            self.session.query(ExecucaoTreinamento.id)
            .filter(ExecucaoTreinamento.status == STATUS_EXECUTANDO).first()
        )
        proximo = None if rodando is not None else (
            self.session.query(ExecucaoTreinamento)
            .filter(ExecucaoTreinamento.status == STATUS_AGUARDANDO)
            .order_by(ExecucaoTreinamento.solicitado_em, ExecucaoTreinamento.id).first()
        )
        if proximo is None:
            self.session.commit()
            return None
        proximo.status = STATUS_EXECUTANDO
        proximo.iniciado_em = agora
        proximo.andamento = "Iniciando"
        self.session.commit()
        return proximo.id

    def encerrar_em_execucao(self) -> int:
        """Serviço `modelo`, ao iniciar: um treinamento que constava em execução parou junto com o processo anterior
        (há um só serviço `modelo`), então é encerrado como falha e deixa de bloquear a fila."""
        agora = self.relogio()
        self.session.execute(text(TRAVA_DO_TREINAMENTO))
        resultado = self.session.execute(
            update(ExecucaoTreinamento).where(ExecucaoTreinamento.status == STATUS_EXECUTANDO)
            .values(status=STATUS_FALHA, concluido_em=agora, etapa_da_falha=ETAPA_INTERNA, andamento=None,
                    erro="Treinamento interrompido: o serviço de treinamento foi reiniciado antes de concluí-lo.")
        )
        self.session.commit()
        return int(resultado.rowcount or 0)

    def resumo(self, id_execucao: int) -> ResumoDoTreinamento:
        execucao = self.session.get(ExecucaoTreinamento, id_execucao)
        if execucao is None:
            raise TreinamentoNaoEncontradoError()
        self.session.refresh(execucao)  # o andamento é gravado pelo serviço `modelo`, em outra conexão
        return self._resumo(execucao)

    def listar(self, limite: int = 10) -> list[ResumoDoTreinamento]:
        """Os treinamentos mais recentes, do mais novo para o mais antigo."""
        execucoes = self.session.query(ExecucaoTreinamento).order_by(ExecucaoTreinamento.id.desc()).limit(limite).all()
        return [self._resumo(execucao) for execucao in execucoes]

    def _resumo(self, e: ExecucaoTreinamento) -> ResumoDoTreinamento:
        modelo = self.session.get(ModeloPreditivo, e.versao) if e.versao is not None else None
        return ResumoDoTreinamento(
            id_execucao=e.id, tipo=e.tipo, disparo=e.disparo, regiao=e.regiao, status=e.status,
            solicitado_em=e.solicitado_em, iniciado_em=e.iniciado_em, concluido_em=e.concluido_em,
            andamento=e.andamento, itens_elegiveis=e.itens_elegiveis, itens_treino=e.itens_treino,
            itens_liberados=e.itens_liberados, itens_bloqueados=e.itens_bloqueados,
            bloqueados_acima_do_limiar=e.bloqueados_acima_do_limiar,
            bloqueados_nao_supera_ingenuo=e.bloqueados_nao_supera_ingenuo,
            bloqueados_avaliacao_insuficiente=e.bloqueados_avaliacao_insuficiente,
            itens_ignorados=e.itens_ignorados, liberados_fora_do_treino=e.liberados_fora_do_treino, avisos=e.avisos,
            etapa_da_falha=e.etapa_da_falha,
            mensagem=MENSAGEM_DA_FALHA.get(e.etapa_da_falha) if e.status == STATUS_FALHA else None,
            erro=e.erro,
            modelo=None if modelo is None else ResumoDoModelo(
                versao=modelo.versao, treinado_em=modelo.treinado_em, vigente=modelo.vigente,
                data_inicio=modelo.data_inicio, corte_validacao=modelo.corte_validacao, corte_teste=modelo.corte_teste,
                data_fim=modelo.data_fim, itens_avaliados=modelo.itens_avaliados,
                amostras_treino=modelo.amostras_treino, amostras_validacao=modelo.amostras_validacao,
                amostras_teste=modelo.amostras_teste, epocas=modelo.epocas, melhor_epoca=modelo.melhor_epoca,
                segundos_por_epoca=modelo.segundos_por_epoca, duracao_segundos=modelo.duracao_segundos,
                mediana_mdape=modelo.mediana_mdape, mediana_mdape_ingenuo=modelo.mediana_mdape_ingenuo,
                mediana_mape=modelo.mediana_mape, mediana_mape_ingenuo=modelo.mediana_mape_ingenuo,
                itens_supera_ingenuo=modelo.itens_supera_ingenuo,
            ),
        )
