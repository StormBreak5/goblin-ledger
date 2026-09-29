from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

from psycopg2.extras import execute_values
from sqlalchemy import func, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.models.item import Item
from src.models.mercado import (
    CICLO_EXECUTANDO,
    CICLO_SUCESSO,
    SITUACAO_ATIVO,
    SITUACAO_EXPIRADO_VENDIDO,
    CicloIngestao,
    EstadoMercado,
    Leilao,
    Reino,
)
from src.scraper.models import DISPARO_RECUPERACAO, ExecutionStatus, HistoricalItemPrice, ScraperExecutionLog
from src.services.ingestao_config import Mercado
from src.services.sanitizacao import LeilaoPadronizado

PAGINA_DE_LEILOES = 5000
CONSULTA_DE_ITENS_EM_LOTES = 5000

_INSERT_LEILOES = (
    f"INSERT INTO {Leilao.__tablename__} (id_leilao_origem, id_reino, item_id, preco_bid, preco_buyout, "
    "preco_unitario, quantidade, tempo_restante, situacao, data_ingestao) VALUES %s "
    "ON CONFLICT (id_reino, id_leilao_origem) DO UPDATE SET item_id = EXCLUDED.item_id, "
    "preco_bid = EXCLUDED.preco_bid, preco_buyout = EXCLUDED.preco_buyout, "
    "preco_unitario = EXCLUDED.preco_unitario, quantidade = EXCLUDED.quantidade, "
    "tempo_restante = EXCLUDED.tempo_restante, situacao = EXCLUDED.situacao, "
    "data_ingestao = EXCLUDED.data_ingestao"
)
_INSERT_HISTORICO = (
    f"INSERT INTO {HistoricalItemPrice.__tablename__} "
    "(item_id, region, timestamp, price, quantity, origem, anomalia, granularidade) "
    "VALUES %s ON CONFLICT (item_id, region, timestamp) DO NOTHING"
)


def _com_fuso_utc(momento: Optional[datetime]) -> Optional[datetime]:
    if momento is None:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _e_da_recuperacao():
    """Só a recuperação automática (e os registros anteriores ao CU10) conta como "backfill" da regra de 48 h: a
    importação do Admin pode cobrir só alguns itens e não recompõe o histórico como um todo."""
    return ScraperExecutionLog.triggered_by.is_(None) | (ScraperExecutionLog.triggered_by == DISPARO_RECUPERACAO)


class MercadoRepository:
    """Acesso a dados do CU09 (reinos, leilões, ciclos de ingestão, frescor e pontos do histórico)."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------ configuração dos mercados

    def garantir_mercados(self, mercados: Iterable[Mercado]) -> None:
        """CU09-C1 (pré-condição / RN11): registra os reinos monitorados e o estado de frescor de cada mercado."""
        for mercado in mercados:
            self.session.execute(
                insert(Reino)
                .values(id_reino=mercado.id_reino, nome=mercado.nome, regiao=mercado.regiao)
                .on_conflict_do_update(index_elements=["id_reino"], set_={"nome": mercado.nome, "regiao": mercado.regiao})
            )
            self.session.execute(
                insert(EstadoMercado)
                .values(mercado=mercado.chave, id_reino=mercado.id_reino)
                .on_conflict_do_nothing(index_elements=["mercado"])
            )

    # ------------------------------------------------------------------ ciclos e intervalo mínimo (RN05)

    def iniciar_ciclo(
        self, chave: str, origem: str, agora: datetime, intervalo: timedelta
    ) -> tuple[Optional[CicloIngestao], Optional[datetime]]:
        """
        CU09-C1 passo 2 (RN05) / CU09-C4 passo 2: se a última requisição ao endpoint foi há menos de `intervalo`,
        devolve (None, horário a partir do qual a coleta é permitida); senão registra o ciclo como EXECUTANDO e o
        devolve. A checagem e o registro são atômicos (trava do PostgreSQL por endpoint), então o worker e o Admin
        nunca coletam o mesmo endpoint ao mesmo tempo.
        """
        self.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:chave))"), {"chave": chave})
        ultima = _com_fuso_utc(
            self.session.query(func.max(CicloIngestao.iniciado_em)).filter(CicloIngestao.endpoint == chave).scalar()
        )
        if ultima is not None and agora - ultima < intervalo:
            self.session.rollback()
            return None, ultima + intervalo

        ciclo = CicloIngestao(endpoint=chave, origem=origem, iniciado_em=agora, status=CICLO_EXECUTANDO)
        self.session.add(ciclo)
        self.session.commit()
        return ciclo, None

    def ultimas_requisicoes(self, chaves: Sequence[str]) -> dict[str, Optional[datetime]]:
        """Início da última requisição de cada endpoint (RN05); None se nunca houve."""
        linhas = (
            self.session.query(CicloIngestao.endpoint, func.max(CicloIngestao.iniciado_em))
            .filter(CicloIngestao.endpoint.in_(list(chaves)))
            .group_by(CicloIngestao.endpoint)
            .all()
        )
        encontradas = {endpoint: _com_fuso_utc(momento) for endpoint, momento in linhas}
        return {chave: encontradas.get(chave) for chave in chaves}

    def ultima_coleta(self) -> Optional[datetime]:
        """Momento da última coleta de histórico concluída, de qualquer origem: um ciclo da Blizzard ou o backfill
        dos .bin da Undermine. É a referência da regra de recuperação de 48 h."""
        ciclo = _com_fuso_utc(
            self.session.query(func.max(CicloIngestao.concluido_em)).filter(CicloIngestao.status == CICLO_SUCESSO).scalar()
        )
        backfill = _com_fuso_utc(
            self.session.query(func.max(ScraperExecutionLog.execution_end))
            .filter(ScraperExecutionLog.status == ExecutionStatus.SUCCESS, _e_da_recuperacao())
            .scalar()
        )  # o backfill grava UTC sem fuso
        momentos = [momento for momento in (ciclo, backfill) if momento is not None]
        return max(momentos) if momentos else None

    def ultimo_backfill_iniciado(self) -> Optional[datetime]:
        """Início da última tentativa de backfill, qualquer que tenha sido o resultado (evita repetir a recuperação
        em sequência quando ela falha)."""
        return _com_fuso_utc(
            self.session.query(func.max(ScraperExecutionLog.execution_start)).filter(_e_da_recuperacao()).scalar()
        )

    # ------------------------------------------------------------------ consolidação (CU09-C3)

    def itens_cadastrados(self, ids: Iterable[int]) -> set[int]:
        """CU09-C3 passo 1: quais dos itens do ciclo já existem em `items`."""
        pendentes = [str(item_id) for item_id in ids]
        encontrados: set[int] = set()
        for inicio in range(0, len(pendentes), CONSULTA_DE_ITENS_EM_LOTES):
            lote = pendentes[inicio:inicio + CONSULTA_DE_ITENS_EM_LOTES]
            linhas = self.session.query(Item.external_item_id).filter(Item.game == "wow", Item.external_item_id.in_(lote))
            encontrados.update(int(linha[0]) for linha in linhas if linha[0].isdigit())
        return encontrados

    def cadastrar_itens(self, ids: Iterable[int]) -> None:
        """CU09-C3-FA1: cadastra o item desconhecido com o identificador e um nome provisório; o nome e o ícone
        vêm depois, do populate_item_details."""
        linhas = [
            {"game": "wow", "external_item_id": str(item_id), "name": f"Item {item_id}", "metadata_info": {"source": "ingestao"}}
            for item_id in ids
        ]
        for inicio in range(0, len(linhas), CONSULTA_DE_ITENS_EM_LOTES):
            self.session.execute(
                insert(Item)
                .values(linhas[inicio:inicio + CONSULTA_DE_ITENS_EM_LOTES])
                .on_conflict_do_nothing(index_elements=["game", "external_item_id"])
            )

    def registrar_leiloes(self, id_reino: int, leiloes: Sequence[LeilaoPadronizado], data_ingestao: datetime) -> None:
        """CU09-C3 passo 2: registra os leilões ativos do ciclo (insere os novos, atualiza os que continuam)."""
        cursor = self.session.connection().connection.cursor()
        try:
            for inicio in range(0, len(leiloes), PAGINA_DE_LEILOES):
                # Um id repetido dentro do mesmo INSERT não pode ser atualizado duas vezes: fica o último.
                pagina = {
                    leilao.id_origem: (
                        leilao.id_origem, id_reino, leilao.item_id, leilao.preco_bid, leilao.preco_buyout,
                        leilao.preco_unitario, leilao.quantidade, leilao.tempo_restante, SITUACAO_ATIVO, data_ingestao,
                    )
                    for leilao in leiloes[inicio:inicio + PAGINA_DE_LEILOES]
                }
                execute_values(cursor, _INSERT_LEILOES, list(pagina.values()), page_size=len(pagina))
        finally:
            cursor.close()

    def classificar_expirados(self, limite: datetime) -> int:
        """CU09-C3 passo 3 (RN04): leilão sem atualização desde antes de `limite` (agora - 48 h) vira Expirado/Vendido,
        sem sair do banco."""
        resultado = self.session.execute(
            update(Leilao)
            .where(Leilao.situacao == SITUACAO_ATIVO, Leilao.data_ingestao < limite)
            .values(situacao=SITUACAO_EXPIRADO_VENDIDO)
        )
        return resultado.rowcount

    def remover_expirados_antigos(self, limite: datetime) -> int:
        """Retenção dos leilões brutos: os Expirado/Vendido anteriores a `limite` saem; o resumo horário em
        historical_item_prices, que é o histórico de longo prazo, permanece."""
        resultado = self.session.query(Leilao).filter(
            Leilao.situacao == SITUACAO_EXPIRADO_VENDIDO, Leilao.data_ingestao < limite
        ).delete(synchronize_session=False)
        return resultado

    def estatisticas_de_volume(self, regiao: str, desde: datetime) -> dict[int, tuple[float, int]]:
        """CU09-C2 passo 4 (RN12): mediana e quantidade dos volumes anteriores (pontos da Blizzard) de cada item."""
        linhas = self.session.execute(
            text(
                "SELECT item_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY quantity) AS mediana, count(*) AS pontos "
                "FROM historical_item_prices "
                "WHERE origem = 'BLIZZARD' AND region = :regiao AND timestamp >= :desde AND quantity IS NOT NULL "
                "GROUP BY item_id"
            ),
            {"regiao": regiao, "desde": desde},
        )
        return {item_id: (float(mediana), pontos) for item_id, mediana, pontos in linhas}

    def registrar_pontos_de_historico(self, pontos: Sequence[tuple]) -> None:
        """CU09-C3: acrescenta ao histórico o valor de mercado e o volume do ciclo. Repetir o mesmo snapshot (mesmo
        Last-Modified) não duplica: a chave (item, região, timestamp) já é única."""
        if not pontos:
            return
        cursor = self.session.connection().connection.cursor()
        try:
            execute_values(cursor, _INSERT_HISTORICO, list(pontos), page_size=10000)
        finally:
            cursor.close()

    # ------------------------------------------------------------------ frescor (RN09 / RN14)

    def registrar_atualizacao(self, chave: str, data_referencia: datetime) -> None:
        """CU09-C3 passo 5 (RN09): data e hora da última atualização do mercado; limpa o "Dados Desatualizados"."""
        self.session.query(EstadoMercado).filter(EstadoMercado.mercado == chave).update(
            {"ultima_atualizacao_em": data_referencia, "desatualizado": False}
        )

    def sinalizar_desatualizado(self, chave: str, quando: datetime) -> None:
        """CU09-C1-FE1 / C2-FE1 / C3-FE1 (RN14): ativa "Dados Desatualizados" para o mercado, mantendo os dados
        do ciclo anterior."""
        self.session.query(EstadoMercado).filter(EstadoMercado.mercado == chave).update(
            {"desatualizado": True, "ultima_falha_em": quando}
        )

    def estados(self) -> list[EstadoMercado]:
        return self.session.query(EstadoMercado).order_by(EstadoMercado.mercado).all()

    # ------------------------------------------------------------------ leitura para o front (CU04 / CU09 obs.)

    def leiloes_do_ultimo_ciclo(self, item_id: int) -> list[tuple[int, int]]:
        """(preço unitário, quantidade) dos leilões do item presentes no último ciclo de cada mercado, só os que têm
        preço de compra."""
        linhas = (
            self.session.query(Leilao.preco_unitario, Leilao.quantidade)
            .join(
                EstadoMercado,
                (EstadoMercado.id_reino == Leilao.id_reino) & (Leilao.data_ingestao == EstadoMercado.ultima_atualizacao_em),
            )
            .filter(Leilao.item_id == item_id, Leilao.preco_unitario.isnot(None))
            .all()
        )
        return [(preco, quantidade) for preco, quantidade in linhas]
