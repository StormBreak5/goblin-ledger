import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Sequence

import psycopg2
from sqlalchemy import text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.item import Item
from src.scraper import backfill
from src.scraper.backfill import (
    BackfillTarget,
    ChunkWriter,
    FonteIndisponivelError,
    FormatoAlteradoError,
    get_items_to_process,
    load_last_seen,
)
from src.scraper.models import (
    DISPARO_RECUPERACAO,
    FALHA_BANCO,
    FALHA_FONTE,
    FALHA_FORMATO,
    FALHA_INTERNA,
    ExecutionStatus,
    ScraperExecutionLog,
)
from src.services import ingestao_config, mensagens, security, validacao
from src.services.erros import ImportacaoEmAndamentoError, ImportacaoNaoEncontradaError, RegiaoOuItemInvalidoError
from src.services.limitador import LimitadorDeIntervalo, intervalo_minimo_configurado

logger = logging.getLogger(__name__)

ID_MAXIMO_DE_ITEM = 2_147_483_647  # a coluna item_id é INTEGER
WOW_TOKEN_ID = 122284  # a Ficha do WoW tem coleta própria (job de 15 min) e o arquivo dela não segue o formato dos itens
# Uma importação que ficou "em andamento" além deste prazo (o processo caiu no meio) deixa de bloquear as novas.
TEMPO_MAXIMO_DA_IMPORTACAO = timedelta(hours=12)
CONSULTA_DE_ITENS_EM_LOTES = 5000

STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
STATUS_CONCLUIDA = "CONCLUIDA"
STATUS_FALHA = "FALHA"

_MENSAGEM_DA_FALHA = {
    FALHA_FONTE: mensagens.FONTE_DE_DADOS_INDISPONIVEL,  # CU10-C1-FE1
    FALHA_BANCO: mensagens.FALHA_NA_IMPORTACAO,  # CU10-C1-FE2
    FALHA_FORMATO: mensagens.FORMATO_DA_FONTE_ALTERADO,  # CU10-C1-FE3
    FALHA_INTERNA: mensagens.FALHA_NA_IMPORTACAO,
}


@dataclass(frozen=True)
class PedidoDeImportacao:
    """CU10-C1 passo 1, já validado: `id_reino` é o reino conectado consultado na Undermine (e a "região" gravada em
    historical_item_prices); `itens` nulo = todos os itens ativos."""
    regiao: str
    id_reino: str
    id_commodities: str
    itens: Optional[tuple[int, ...]] = None


@dataclass
class ResumoDaImportacao:
    """CU10-C1 passo 10: o que a importação fez, com a mensagem do fluxo de exceção quando falhou."""
    id_execucao: int
    status: str  # EM_ANDAMENTO, CONCLUIDA ou FALHA
    disparo: Optional[str]
    regiao: Optional[str]
    itens_solicitados: Optional[int]
    itens_processados: int
    itens_cadastrados: int
    itens_sem_dados: int
    itens_com_erro: int
    registros_importados: int
    registros_descartados: int
    registros_duplicados: int
    iniciada_em: datetime
    concluida_em: Optional[datetime]
    etapa_da_falha: Optional[str] = None
    mensagem: Optional[str] = None
    erro: Optional[str] = None


def _id_de_item(valor: Any) -> Optional[int]:
    """Aceita inteiro ou texto numérico; qualquer outra coisa, ou fora da faixa, é inválida."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, str) and valor.strip().isdigit():
        valor = int(valor.strip())
    if not isinstance(valor, int) or not 1 <= valor <= ID_MAXIMO_DE_ITEM or valor == WOW_TOKEN_ID:
        return None
    return valor


class ImportacaoHistoricoService:
    """CU10-C1 – Importar histórico de preços (RF11): valida o pedido, baixa os arquivos da Undermine Exchange, harmoniza
    (RN16) e grava, mantendo o registro de cada execução em `scraper_execution_logs`."""

    def __init__(
        self,
        session: Session,
        relogio: Callable[[], datetime] = security.agora,
        limitador: Optional[LimitadorDeIntervalo] = None,
        preencher_itens_novos: Optional[Callable[[], None]] = None,
    ):
        self.session = session
        self.relogio = relogio
        self._limitador = limitador
        self._preencher_itens_novos = preencher_itens_novos

    # ------------------------------------------------------------------ passo 2: validação

    def validar(self, regiao: str, reino: Optional[int], itens: Optional[Sequence[Any]]) -> PedidoDeImportacao:
        """
        CU10-C1 passo 2 e FA1: região US/EU (RN11) com um reino conectado (o informado ou o primeiro monitorado da
        região) e identificadores de item válidos. Sem itens, importa todos os itens ativos.
        """
        regiao_normalizada = validacao.normalizar_regiao(regiao)
        if regiao_normalizada is None:
            raise RegiaoOuItemInvalidoError()

        if reino is None:
            monitorados = [
                mercado for mercado in ingestao_config.carregar_mercados()
                if mercado.tipo == ingestao_config.TIPO_LEILOES and mercado.regiao == regiao_normalizada
            ]
            if not monitorados:
                raise RegiaoOuItemInvalidoError()
            reino = monitorados[0].id_reino
        elif isinstance(reino, bool) or not isinstance(reino, int) or reino < 1:
            raise RegiaoOuItemInvalidoError()

        ids: Optional[tuple[int, ...]] = None
        if itens:
            validos = [_id_de_item(valor) for valor in itens]
            if any(valor is None for valor in validos):
                raise RegiaoOuItemInvalidoError()
            ids = tuple(dict.fromkeys(validos))  # sem repetidos, na ordem informada

        return PedidoDeImportacao(
            regiao=regiao_normalizada,
            id_reino=str(reino),
            id_commodities=str(ingestao_config.COMMODITIES_ID_POR_REGIAO[regiao_normalizada]),
            itens=ids,
        )

    # ------------------------------------------------------------------ registro da execução

    def registrar_inicio(self, pedido: PedidoDeImportacao, disparo: str) -> int:
        """Abre o registro da execução. Só uma importação roda por vez: a checagem e o registro são atômicos (trava do
        PostgreSQL), então o Admin e a recuperação do worker nunca importam ao mesmo tempo."""
        agora = self.relogio().replace(tzinfo=None)
        self.session.execute(text("SELECT pg_advisory_xact_lock(hashtext('importacao_historico'))"))
        self.session.execute(
            update(ScraperExecutionLog)
            .where(
                ScraperExecutionLog.status == ExecutionStatus.RUNNING,
                ScraperExecutionLog.execution_start < agora - TEMPO_MAXIMO_DA_IMPORTACAO,
            )
            .values(
                status=ExecutionStatus.FAILED, execution_end=agora, failure_stage=FALHA_INTERNA,
                error_message="Importação interrompida: o processo parou antes de concluí-la.",
            )
        )
        em_andamento = (
            self.session.query(ScraperExecutionLog.id).filter(ScraperExecutionLog.status == ExecutionStatus.RUNNING).first()
        )
        if em_andamento is not None:
            self.session.rollback()
            raise ImportacaoEmAndamentoError()

        log = ScraperExecutionLog(
            execution_start=agora, status=ExecutionStatus.RUNNING, items_processed=0, records_inserted=0,
            triggered_by=disparo, region=pedido.id_reino,
            items_requested=len(pedido.itens) if pedido.itens is not None else None,
            items_created=0, items_without_data=0, items_failed=0, records_discarded=0, records_duplicated=0,
        )
        self.session.add(log)
        self.session.commit()
        return log.id

    def resumo(self, id_execucao: int) -> ResumoDaImportacao:
        log = self.session.get(ScraperExecutionLog, id_execucao)
        if log is None:
            raise ImportacaoNaoEncontradaError()
        self.session.refresh(log)  # o progresso é gravado por outra conexão durante a importação
        return _resumo_do_log(log)

    def listar(self, limite: int = 10) -> list[ResumoDaImportacao]:
        """As importações mais recentes, da mais nova para a mais antiga (só as feitas a partir do CU10)."""
        logs = (
            self.session.query(ScraperExecutionLog)
            .filter(ScraperExecutionLog.triggered_by.isnot(None))
            .order_by(ScraperExecutionLog.id.desc())
            .limit(limite)
            .all()
        )
        return [_resumo_do_log(log) for log in logs]

    # ------------------------------------------------------------------ passos 3 a 10

    def executar(self, id_execucao: int, pedido: PedidoDeImportacao, *, incremental: bool = False) -> ResumoDaImportacao:
        """
        Executa a importação já registrada. Falhas previstas viram o resultado FALHA (com a etapa e o erro) e nunca
        propagam: FE1 (fonte indisponível) e FE3 (formato alterado) interrompem e mantêm o que já foi gravado; FE2
        (banco) desfaz tudo. `incremental` (recuperação automática) grava só o que é mais novo que o último ponto de
        cada item; a importação do Admin não usa o atalho, para contar os duplicados com exatidão.
        """
        writer = ChunkWriter(self.session, pedido.id_reino, {}, incremental=incremental)
        try:
            targets = self._alvos(pedido, incremental)
            writer.last_seen = load_last_seen(self.session, pedido.id_reino) if incremental else {}
            writer.on_progress = self._registrador_de_progresso(id_execucao)
            self.session.execute(
                update(ScraperExecutionLog).where(ScraperExecutionLog.id == id_execucao).values(items_requested=len(targets))
            )
            self.session.commit()

            try:
                download = backfill.importar(
                    targets, pedido.id_reino, writer,
                    limitador=self._limitador or LimitadorDeIntervalo(intervalo_minimo_configurado()),
                    commodity_id=pedido.id_commodities,
                )
            except (FonteIndisponivelError, FormatoAlteradoError) as e:
                self.session.commit()  # FE1 / FE3: mantém os registros já gravados
                etapa = FALHA_FONTE if isinstance(e, FonteIndisponivelError) else FALHA_FORMATO
                logger.error("CU10-C1-%s: %s", "FE1" if etapa == FALHA_FONTE else "FE3", e)
                return self._finalizar(id_execucao, writer, etapa, str(e), gravado=True)
            self.session.commit()  # passo 9
        except Exception as e:  # FE2: falha na gravação; nada fica persistido
            self.session.rollback()
            etapa = FALHA_BANCO if isinstance(e, (SQLAlchemyError, psycopg2.Error)) else FALHA_INTERNA
            logger.exception("CU10-C1-FE2: a importação foi desfeita.")
            return self._finalizar(id_execucao, writer, etapa, str(e), gravado=False)

        logger.info(
            "CU10-C1: importação concluída. %d itens processados, %d registros importados, %d descartados, %d duplicados. "
            "Tempos: download+decodificação=%.1fs, gravação=%.1fs.",
            writer.items_processed, writer.records_inserted, writer.records_discarded, writer.records_duplicated,
            download, writer.write_seconds,
        )
        resumo = self._finalizar(id_execucao, writer, None, None, gravado=True)
        self._preencher_itens(writer.items_created)
        return resumo

    def recuperar(self) -> None:
        """Recuperação automática (worker, mais de 48 h sem coleta): importa de forma incremental os itens ativos de
        cada reino monitorado. Se outra importação estiver em andamento, não faz nada."""
        for mercado in ingestao_config.carregar_mercados():
            if mercado.tipo != ingestao_config.TIPO_LEILOES:
                continue
            pedido = self.validar(mercado.regiao, mercado.id_reino, None)
            try:
                id_execucao = self.registrar_inicio(pedido, DISPARO_RECUPERACAO)
            except ImportacaoEmAndamentoError:
                logger.info("Recuperação do histórico adiada: já existe uma importação em andamento.")
                return
            self.executar(id_execucao, pedido, incremental=True)

    # ------------------------------------------------------------------ apoio

    def _alvos(self, pedido: PedidoDeImportacao, incremental: bool) -> list[BackfillTarget]:
        """Itens a baixar, com o que o ORM sabe deles. Fora da recuperação o ETag é ignorado: um 304 devolveria um
        arquivo vazio e o resumo não teria como contar os registros duplicados."""

        def metadados(item: Item) -> dict:
            dados = dict(item.metadata_info or {})
            if not incremental:
                dados.pop("last_etag", None)
            return dados

        if pedido.itens is None:
            return [
                BackfillTarget(pk=item.id, item_id=int(item.external_item_id), metadata=metadados(item))
                for item in get_items_to_process(self.session)
                if item.external_item_id.isdigit() and int(item.external_item_id) != WOW_TOKEN_ID
            ]

        existentes: dict[int, Item] = {}
        textos = [str(item_id) for item_id in pedido.itens]
        for inicio in range(0, len(textos), CONSULTA_DE_ITENS_EM_LOTES):
            consulta = self.session.query(Item).filter(
                Item.game == "wow", Item.external_item_id.in_(textos[inicio:inicio + CONSULTA_DE_ITENS_EM_LOTES])
            )
            existentes.update({int(item.external_item_id): item for item in consulta if item.external_item_id.isdigit()})
        return [
            BackfillTarget(pk=existentes[item_id].id, item_id=item_id, metadata=metadados(existentes[item_id]))
            if item_id in existentes else BackfillTarget(pk=None, item_id=item_id)  # CU10-C1-FA2
            for item_id in pedido.itens
        ]

    def _registrador_de_progresso(self, id_execucao: int) -> Callable[[ChunkWriter], None]:
        """Acompanhamento da importação em andamento: a transação dos dados só é confirmada no fim, então o progresso é
        gravado por uma conexão à parte."""
        engine = self.session.get_bind()

        def registrar(writer: ChunkWriter) -> None:
            try:
                with engine.begin() as conexao:
                    conexao.execute(
                        update(ScraperExecutionLog).where(ScraperExecutionLog.id == id_execucao).values(
                            items_processed=writer.items_processed, records_inserted=writer.records_inserted,
                            records_discarded=writer.records_discarded, records_duplicated=writer.records_duplicated,
                            items_created=writer.items_created, items_without_data=writer.items_without_data,
                            items_failed=writer.items_failed,
                        )
                    )
            except SQLAlchemyError:
                logger.warning("CU10-C1: não foi possível registrar o progresso da importação.", exc_info=True)

        return registrar

    def _finalizar(
        self, id_execucao: int, writer: ChunkWriter, etapa_da_falha: Optional[str], erro: Optional[str], gravado: bool
    ) -> ResumoDaImportacao:
        """Fecha o registro da execução. `gravado` falso (FE2): nada foi persistido, então os contadores de gravação
        ficam em zero."""
        log = self.session.get(ScraperExecutionLog, id_execucao)
        if log is None:  # o banco não estava acessível nem para abrir o registro
            raise ImportacaoNaoEncontradaError()
        try:
            log.status = ExecutionStatus.SUCCESS if etapa_da_falha is None else ExecutionStatus.FAILED
            log.execution_end = self.relogio().replace(tzinfo=None)
            log.items_processed = writer.items_processed
            log.items_without_data = writer.items_without_data
            log.items_failed = writer.items_failed
            log.items_created = writer.items_created if gravado else 0
            log.records_inserted = writer.records_inserted if gravado else 0
            log.records_discarded = writer.records_discarded if gravado else 0
            log.records_duplicated = writer.records_duplicated if gravado else 0
            log.failure_stage = etapa_da_falha
            log.error_message = erro
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception("CU10-C1: não foi possível fechar o registro da importação %s.", id_execucao)
            raise
        return _resumo_do_log(log)

    def _preencher_itens(self, itens_cadastrados: int) -> None:
        """CU10-C1-FA2: itens cadastrados nascem com nome provisório; completa o nome e o ícone (melhor esforço)."""
        if not itens_cadastrados or self._preencher_itens_novos is None:
            return
        try:
            self._preencher_itens_novos()
        except Exception:
            logger.exception("Não foi possível preencher o nome e o ícone dos itens novos; fica para a sincronização diária.")


def _resumo_do_log(log: ScraperExecutionLog) -> ResumoDaImportacao:
    if log.status == ExecutionStatus.RUNNING:
        status = STATUS_EM_ANDAMENTO
    elif log.status == ExecutionStatus.SUCCESS:
        status = STATUS_CONCLUIDA
    else:
        status = STATUS_FALHA
    return ResumoDaImportacao(
        id_execucao=log.id,
        status=status,
        disparo=log.triggered_by,
        regiao=log.region,
        itens_solicitados=log.items_requested,
        itens_processados=log.items_processed or 0,
        itens_cadastrados=log.items_created or 0,
        itens_sem_dados=log.items_without_data or 0,
        itens_com_erro=log.items_failed or 0,
        registros_importados=log.records_inserted or 0,
        registros_descartados=log.records_discarded or 0,
        registros_duplicados=log.records_duplicated or 0,
        iniciada_em=log.execution_start,
        concluida_em=log.execution_end,
        etapa_da_falha=log.failure_stage,
        mensagem=_MENSAGEM_DA_FALHA.get(log.failure_stage) if status == STATUS_FALHA else None,
        erro=log.error_message,
    )
