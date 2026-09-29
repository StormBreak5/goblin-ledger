"""
Plano de testes do CU10 – Cadastrar Dados Passados, Cenário 01 (importar histórico de preços):
estratégia de gravação do backfill (lotes, incremental, origem do item e atomicidade).

Rodam contra um PostgreSQL temporário (ver tests/conftest.py), porque a gravação usa `ON CONFLICT`.
O download é substituído por uma fonte falsa: nenhum teste acessa a Undermine Exchange.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.scraper import backfill
from src.scraper.models import ExecutionStatus, HistoricalItemPrice, ScraperExecutionLog

REGION = "3209"
COMMODITY_REGION = "32512"


def _days(count: int) -> list[datetime]:
    return [datetime(2026, 6, 1) + timedelta(days=offset) for offset in range(count)]


def _parsed(days: list[datetime]) -> dict:
    """Mesma forma devolvida por `decompress_and_parse` (datas em milissegundos)."""
    return {
        "snapshots": [],
        "daily": [
            {"snapshot": int(day.replace(tzinfo=timezone.utc).timestamp() * 1000), "price": 100000, "quantity": 5}
            for day in days
        ],
    }


@pytest.fixture
def fake_source(mocker):
    """Substitui o download. `series[item_id] = (datas, origem)`; `calls` guarda os alvos consultados."""
    series: dict[int, tuple[list[datetime], str]] = {}
    calls: list[backfill.BackfillTarget] = []

    async def fake_fetch(http_session, region_id, target):
        calls.append(target)
        days, source = series[target.item_id]
        return 200, _parsed(days), f'"etag-{target.item_id}-{len(days)}"', None, source

    mocker.patch.object(backfill, "fetch_item_history", fake_fetch)
    mocker.patch.object(backfill, "REQUEST_DELAY_SECONDS", 0)
    return series, calls


def _total_de_linhas(db_session) -> int:
    return db_session.query(HistoricalItemPrice).count()


def test_cu10_c1_fluxo_principal_grava_em_paginas_na_mesma_transacao(db_session, add_item, fake_source, mocker, pg_engine):
    series, _ = fake_source
    items = []
    for numero in range(1, 5):
        items.append(add_item(9000 + numero, f"Item {numero}"))
        series[9000 + numero] = (_days(30), REGION)
    mocker.patch.object(backfill, "CHUNK_SIZE", 2)  # 2 lotes de 2 itens (60 linhas cada)
    mocker.patch.object(backfill, "INSERT_PAGE_SIZE", 25)  # 3 páginas por lote: 25 + 25 + 10
    paginas = mocker.spy(backfill, "execute_values")

    visiveis_a_outras_conexoes: list[int] = []
    gravar_lote = backfill.ChunkWriter.__call__

    def gravar_e_espiar(self, results):
        gravar_lote(self, results)
        with pg_engine.connect() as outra_conexao:
            visiveis_a_outras_conexoes.append(
                outra_conexao.execute(text("select count(*) from historical_item_prices")).scalar()
            )

    mocker.patch.object(backfill.ChunkWriter, "__call__", gravar_e_espiar)

    backfill.run_backfill(db_session, items, REGION)

    assert [len(chamada.args[2]) for chamada in paginas.call_args_list] == [25, 25, 10, 25, 25, 10]
    assert visiveis_a_outras_conexoes == [0, 0]  # nada é confirmado antes do fim: uma única transação
    assert _total_de_linhas(db_session) == 4 * 30
    log = db_session.query(ScraperExecutionLog).one()
    assert (log.status, log.items_processed, log.records_inserted) == (ExecutionStatus.SUCCESS, 4, 120)


def test_cu10_c1_fluxo_principal_insere_somente_registros_novos(db_session, add_item, fake_source, mocker):
    series, _ = fake_source
    item = add_item(9101, "Copper Ore")
    series[9101] = (_days(10), REGION)  # 01/06 a 10/06
    backfill.run_backfill(db_session, [item], REGION)
    assert _total_de_linhas(db_session) == 10

    series[9101] = (_days(13), REGION)  # a fonte ganhou 11/06, 12/06 e 13/06
    enviadas = mocker.spy(backfill, "_insert_rows")
    backfill.run_backfill(db_session, [item], REGION)

    # Só segue para o banco o que é mais novo que (último ponto - margem de 2 dias): 09/06 a 13/06.
    assert len(enviadas.call_args.args[1]) == 5
    assert _total_de_linhas(db_session) == 13
    segundo_log = db_session.query(ScraperExecutionLog).order_by(ScraperExecutionLog.id.desc()).first()
    assert segundo_log.records_inserted == 3  # o que já existia continua sendo ignorado (ON CONFLICT)


def test_cu10_c1_fluxo_principal_registra_origem_do_item(db_session, add_item, fake_source):
    series, chamadas = fake_source
    item = add_item(9201, "Linen Cloth")
    series[9201] = (_days(3), COMMODITY_REGION)  # não existe no reino: veio do fallback de commodities

    backfill.run_backfill(db_session, [item], REGION)

    db_session.refresh(item)
    assert item.metadata_info["source_region"] == COMMODITY_REGION
    assert item.metadata_info["last_etag"]

    backfill.run_backfill(db_session, [item], REGION)
    assert chamadas[-1].source_region == COMMODITY_REGION  # a segunda rodada já conhece a origem

    origens = lambda preferida: [origem for origem, _ in backfill.candidate_urls(9201, REGION, preferida)]
    assert origens(COMMODITY_REGION) == [COMMODITY_REGION, REGION]  # sem a requisição que daria 404
    assert origens(None) == [REGION, COMMODITY_REGION]
    assert origens("origem-desconhecida") == [REGION, COMMODITY_REGION]
    assert [origem for origem, _ in backfill.candidate_urls(122284, REGION, None)] == ["global"]  # Ficha do WoW


def test_cu10_c1_fe2_falha_de_banco_desfaz_importacao_sem_registros_parciais(db_session, add_item, fake_source, mocker):
    series, _ = fake_source
    items = []
    for numero in range(1, 5):
        items.append(add_item(9300 + numero, f"Item {numero}"))
        series[9300 + numero] = (_days(5), REGION)
    mocker.patch.object(backfill, "CHUNK_SIZE", 2)

    gravar_linhas = backfill._insert_rows
    chamadas = {"total": 0}

    def cai_no_segundo_lote(session, rows):
        chamadas["total"] += 1
        if chamadas["total"] == 2:
            raise OperationalError("INSERT INTO historical_item_prices", {}, Exception("connection lost"))
        return gravar_linhas(session, rows)

    mocker.patch.object(backfill, "_insert_rows", cai_no_segundo_lote)

    backfill.run_backfill(db_session, items, REGION)

    assert _total_de_linhas(db_session) == 0  # o primeiro lote também foi desfeito
    for item in items:
        db_session.refresh(item)
        assert "last_etag" not in (item.metadata_info or {})  # e os ETags não avançaram
    log = db_session.query(ScraperExecutionLog).one()
    assert log.status == ExecutionStatus.FAILED
    assert "connection lost" in log.error_message
