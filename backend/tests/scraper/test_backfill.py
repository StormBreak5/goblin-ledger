"""
Plano de testes do CU10 – Cadastrar Dados Passados, Cenário 01 (importar histórico de preços):
estratégia de gravação da importação (lotes, incremental, origem do item, granularidade, atomicidade), o limitador de
ritmo (RN23 / FA3) e a decodificação do arquivo da Undermine Exchange (RN16).

Rodam contra um PostgreSQL temporário (ver tests/conftest.py), porque a gravação usa `ON CONFLICT`.
O download é substituído por uma fonte falsa: nenhum teste acessa a Undermine Exchange.
Os fluxos do cenário, do pedido do Admin até as mensagens, estão em tests/integration/test_cu10_c1_importar_historico.py.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from helpers_historico import REGIAO, REGIAO_DAS_COMMODITIES, arquivo_bin, dados_decodificados, dias
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.scraper import backfill
from src.scraper.models import (
    DISPARO_ADMIN,
    FALHA_BANCO,
    ExecutionStatus,
    HistoricalItemPrice,
    ScraperExecutionLog,
)
from src.scraper.parser import parse_item_state
from src.services.importacao_historico import STATUS_CONCLUIDA, STATUS_FALHA, ImportacaoHistoricoService
from src.services.limitador import LimitadorDeIntervalo


def _importar(db_session, itens, incremental: bool = True):
    """Pedido do Admin (região US, reino 3209) executado de ponta a ponta pelo serviço."""
    servico = ImportacaoHistoricoService(db_session)
    pedido = servico.validar("US", 3209, [int(item.external_item_id) for item in itens])
    return servico.executar(servico.registrar_inicio(pedido, DISPARO_ADMIN), pedido, incremental=incremental)


def _total_de_linhas(db_session) -> int:
    return db_session.query(HistoricalItemPrice).count()


def test_cu10_c1_fluxo_principal_grava_em_paginas_na_mesma_transacao(db_session, add_item, fonte_falsa, mocker, pg_engine):
    items = []
    for numero in range(1, 5):
        items.append(add_item(9000 + numero, f"Item {numero}"))
        fonte_falsa.com_dias(9000 + numero, dias(30))
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

    resumo = _importar(db_session, items)

    assert [len(chamada.args[2]) for chamada in paginas.call_args_list] == [25, 25, 10, 25, 25, 10]
    assert visiveis_a_outras_conexoes == [0, 0]  # nada é confirmado antes do fim: uma única transação
    assert _total_de_linhas(db_session) == 4 * 30
    log = db_session.query(ScraperExecutionLog).one()
    assert (log.status, log.items_processed, log.records_inserted) == (ExecutionStatus.SUCCESS, 4, 120)
    assert (resumo.status, resumo.registros_importados) == (STATUS_CONCLUIDA, 120)


def test_cu10_c1_fluxo_principal_insere_somente_registros_novos(db_session, add_item, fonte_falsa, mocker):
    item = add_item(9101, "Copper Ore")
    fonte_falsa.com_dias(9101, dias(10))  # 01/06 a 10/06
    _importar(db_session, [item])
    assert _total_de_linhas(db_session) == 10

    fonte_falsa.com_dias(9101, dias(13))  # a fonte ganhou 11/06, 12/06 e 13/06
    enviadas = mocker.spy(backfill, "_insert_rows")
    resumo = _importar(db_session, [item])  # recuperação automática: incremental

    # Só segue para o banco o que é mais novo que (último ponto - margem de 2 dias): 09/06 a 13/06.
    assert len(enviadas.call_args.args[1]) == 5
    assert _total_de_linhas(db_session) == 13
    assert resumo.registros_importados == 3  # o que já existia continua sendo ignorado (ON CONFLICT)
    assert resumo.registros_duplicados == 10  # 8 abaixo do corte + 2 dentro da margem que já estavam gravados


def test_cu10_c1_fluxo_principal_registra_origem_do_item(db_session, add_item, fonte_falsa):
    item = add_item(9201, "Linen Cloth")
    fonte_falsa.com_dias(9201, dias(3), origem=REGIAO_DAS_COMMODITIES)  # não existe no reino: veio do fallback de commodities

    _importar(db_session, [item])

    db_session.refresh(item)
    assert item.metadata_info["source_region"] == REGIAO_DAS_COMMODITIES
    assert item.metadata_info["last_etag"]

    _importar(db_session, [item])
    assert fonte_falsa.chamadas[-1].source_region == REGIAO_DAS_COMMODITIES  # a segunda rodada já conhece a origem

    origens = lambda preferida: [origem for origem, _ in backfill.candidate_urls(9201, REGIAO, preferida)]
    assert origens(REGIAO_DAS_COMMODITIES) == [REGIAO_DAS_COMMODITIES, REGIAO]  # sem a requisição que daria 404
    assert origens(None) == [REGIAO, REGIAO_DAS_COMMODITIES]
    assert origens("origem-desconhecida") == [REGIAO, REGIAO_DAS_COMMODITIES]
    europa = backfill.candidate_urls(9201, "1305", None, commodity_id="32513")  # as commodities seguem a região do pedido
    assert [origem for origem, _ in europa] == ["1305", "32513"]


def test_cu10_c1_fe2_falha_de_banco_desfaz_importacao_sem_registros_parciais(db_session, add_item, fonte_falsa, mocker):
    items = []
    for numero in range(1, 5):
        items.append(add_item(9300 + numero, f"Item {numero}"))
        fonte_falsa.com_dias(9300 + numero, dias(5))
    mocker.patch.object(backfill, "CHUNK_SIZE", 2)

    gravar_linhas = backfill._insert_rows
    chamadas = {"total": 0}

    def cai_no_segundo_lote(session, rows):
        chamadas["total"] += 1
        if chamadas["total"] == 2:
            raise OperationalError("INSERT INTO historical_item_prices", {}, Exception("connection lost"))
        return gravar_linhas(session, rows)

    mocker.patch.object(backfill, "_insert_rows", cai_no_segundo_lote)

    resumo = _importar(db_session, items)

    assert _total_de_linhas(db_session) == 0  # o primeiro lote também foi desfeito
    for item in items:
        db_session.refresh(item)
        assert "last_etag" not in (item.metadata_info or {})  # e os ETags não avançaram
    log = db_session.query(ScraperExecutionLog).one()
    assert log.status == ExecutionStatus.FAILED
    assert "connection lost" in log.error_message
    assert (resumo.status, resumo.etapa_da_falha, resumo.registros_importados) == (STATUS_FALHA, FALHA_BANCO, 0)


def test_cu10_c1_fluxo_principal_descarta_registros_com_data_invalida(db_session, add_item, fonte_falsa, mocker, caplog):
    """CU10-C1 passo 7: datas inválidas e valores negativos não chegam ao banco nem contaminam o filtro incremental."""
    item = add_item(9401, "Silk Cloth")
    agora = datetime.now(timezone.utc)
    invalidos_em_ms = [
        107365857060000,  # ano 5372 (tempo em segundos lido como minutos): no Linux converte sem erro, no Windows dá OSError
        int((agora + timedelta(days=30)).timestamp() * 1000),  # no futuro
        int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),  # antes do lançamento do jogo
    ]
    series = {"dias": dias(3)}

    async def fonte_com_lixo(http_session, region_id, target, **_):
        dados = dados_decodificados(series["dias"])
        dados["snapshots"] = [{"snapshot": ms, "price": 1, "quantity": 1} for ms in invalidos_em_ms]
        dados["daily"].append({"snapshot": dados["daily"][0]["snapshot"] + 86_400_000 * 100, "price": -5, "quantity": 1})
        return 200, dados, f'"etag-{len(series["dias"])}"', None, REGIAO

    mocker.patch.object(backfill, "fetch_item_history", fonte_com_lixo)

    with caplog.at_level(logging.WARNING, logger="src.scraper.backfill"):
        resumo = _importar(db_session, [item])

    datas = [linha.timestamp for linha in db_session.query(HistoricalItemPrice).order_by(HistoricalItemPrice.timestamp)]
    assert datas == dias(3)
    assert "4 price points with an invalid date" in caplog.text
    assert resumo.registros_descartados == 4  # as 3 datas inválidas e o preço negativo

    # A fonte ganha um dia real: entra normalmente, o que não aconteceria se uma data absurda fosse o "último ponto".
    series["dias"] = dias(4)
    _importar(db_session, [item])
    assert _total_de_linhas(db_session) == 4


def test_cu10_c1_fluxo_principal_marca_a_granularidade_de_cada_registro_rn16(db_session, add_item, fonte_falsa):
    item = add_item(9501, "Peacebloom")
    horarios = [datetime(2026, 6, 10, 13, 0) + timedelta(hours=h) for h in range(3)]
    fonte_falsa.com_dias(9501, dias(2), horarios=horarios)

    _importar(db_session, [item])

    linhas = db_session.query(HistoricalItemPrice).order_by(HistoricalItemPrice.timestamp).all()
    assert [(linha.timestamp, linha.granularidade) for linha in linhas] == [
        (dias(1)[0], "DIARIA"), (dias(2)[1], "DIARIA"),
        (horarios[0], "HORARIA"), (horarios[1], "HORARIA"), (horarios[2], "HORARIA"),
    ]
    assert {linha.origem for linha in linhas} == {"UNDERMINE"}


def test_cu10_c1_fluxo_principal_conta_os_duplicados_de_forma_exata(db_session, add_item, fonte_falsa):
    item = add_item(9601, "Mageroyal")
    fonte_falsa.com_dias(9601, dias(10))
    primeira = _importar(db_session, [item], incremental=False)

    fonte_falsa.com_dias(9601, dias(12))
    segunda = _importar(db_session, [item], incremental=False)  # importação do Admin: nada é filtrado antes do banco

    assert (primeira.registros_importados, primeira.registros_duplicados) == (10, 0)
    assert (segunda.registros_importados, segunda.registros_duplicados) == (2, 10)


def test_cu10_c1_rn16_a_importacao_le_o_tempo_dos_snapshots_em_segundos():
    """O tempo dos snapshots horários vem em segundos Unix (lido como minutos caía no ano 5372 e era descartado) e o
    dos agregados diários em dias desde 1970."""
    momento = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    dia = datetime(2026, 9, 13, tzinfo=timezone.utc)
    conteudo = arquivo_bin(
        snapshots=[(int(momento.timestamp()), 25, 3)],
        diarios=[(int(dia.timestamp() // 86400), 20, 8)],
    )

    dados = parse_item_state(conteudo)

    [snapshot] = dados["snapshots"]
    assert datetime.fromtimestamp(snapshot["snapshot"] / 1000, tz=timezone.utc) == momento
    assert (snapshot["price"], snapshot["quantity"]) == (2500, 3)  # preços vêm em unidades de 100 cobre (RN01)
    [diario] = dados["daily"]
    assert datetime.fromtimestamp(diario["snapshot"] / 1000, tz=timezone.utc) == dia
    assert (diario["price"], diario["quantity"]) == (2000, 8)


# ---------------------------------------------------------------------- CU10-C1-FA3 / RN23: ritmo das requisições


def test_cu10_c1_fa3_limitador_espera_o_intervalo_minimo_entre_requisicoes():
    relogio = {"agora": 100.0}
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        relogio["agora"] += segundos

    limitador = LimitadorDeIntervalo(0.5, relogio=lambda: relogio["agora"], dormir=dormir)
    inicios: list[float] = []

    async def requisicao():
        await limitador.aguardar()
        inicios.append(relogio["agora"])

    async def cinco_requisicoes_ao_mesmo_tempo():
        await asyncio.gather(*[requisicao() for _ in range(5)])

    asyncio.run(cinco_requisicoes_ao_mesmo_tempo())

    assert inicios == [100.0, 100.5, 101.0, 101.5, 102.0]  # a primeira sai na hora; cada uma espera o intervalo da anterior
    assert esperas == [0.5, 0.5, 0.5, 0.5]


def test_cu10_c1_fa3_intervalo_zero_desliga_a_espera():
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)

    limitador = LimitadorDeIntervalo(0, dormir=dormir)

    async def duas() -> None:
        await limitador.aguardar()
        await limitador.aguardar()

    asyncio.run(duas())
    assert esperas == []


class _RespostaFalsa:
    def __init__(self, status: int, corpo: bytes = b""):
        self.status = status
        self.headers = {"ETag": '"abc"'}
        self._corpo = corpo

    async def read(self) -> bytes:
        return self._corpo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _SessaoHttpFalsa:
    def __init__(self, eventos: list, respostas: list):
        self.eventos = eventos
        self.respostas = respostas

    def get(self, url, headers=None):
        self.eventos.append(("requisicao", url))
        return self.respostas.pop(0)


def test_cu10_c1_fa3_cada_requisicao_espera_o_limitador_inclusive_a_da_commodity():
    """O item de commodity gasta duas requisições (reino local 404, depois o fallback): as duas são espaçadas."""
    eventos: list = []

    class LimitadorQueRegistra:
        async def aguardar(self) -> None:
            eventos.append(("espera", None))

    conteudo = arquivo_bin(snapshots=[], diarios=[(20_000, 20, 8)])
    http = _SessaoHttpFalsa(eventos, [_RespostaFalsa(404), _RespostaFalsa(200, conteudo)])

    status, dados, etag, erro, origem = asyncio.run(
        backfill.fetch_item_history(
            http, REGIAO, backfill.BackfillTarget(pk=None, item_id=9701), limitador=LimitadorQueRegistra()
        )
    )

    assert status == 200 and origem == REGIAO_DAS_COMMODITIES
    assert [tipo for tipo, _ in eventos] == ["espera", "requisicao", "espera", "requisicao"]  # espera antes de cada uma


def test_cu10_c1_fe3_arquivo_que_nao_decodifica_e_distinto_de_falha_de_rede():
    http = _SessaoHttpFalsa([], [_RespostaFalsa(200, b"\x05\x01")])  # cortado no meio do cabeçalho

    status, dados, etag, erro, origem = asyncio.run(
        backfill.fetch_item_history(http, REGIAO, backfill.BackfillTarget(pk=None, item_id=9702))
    )

    assert status == backfill.STATUS_FORMATO_INVALIDO and dados is None
    assert "9702.bin" in erro


def test_cu10_c1_a_importacao_do_admin_ignora_o_etag_para_contar_os_duplicados(db_session, add_item, fonte_falsa):
    item = add_item(9801, "Ashwood")
    fonte_falsa.com_dias(9801, dias(6))
    fonte_falsa.respeita_etag = True  # com o ETag da importação anterior a fonte devolveria 304, sem arquivo
    _importar(db_session, [item], incremental=False)

    repetida = _importar(db_session, [item], incremental=False)
    recuperacao = _importar(db_session, [item], incremental=True)

    assert (repetida.registros_importados, repetida.registros_duplicados) == (0, 6)  # o arquivo foi baixado de novo
    assert recuperacao.registros_duplicados == 0  # a recuperação usa o ETag: nada foi baixado, nada a contar


def test_cu10_c1_os_pontos_da_blizzard_nao_escondem_o_historico_ainda_nao_importado(db_session, add_item, fonte_falsa):
    """Um item que só tem pontos do ciclo da Blizzard (mais novos) precisa receber o histórico inteiro da Undermine."""
    item = add_item(9802, "Sungrass")
    db_session.add(
        HistoricalItemPrice(
            item_id=9802, region=REGIAO, timestamp=dias(1)[0] + timedelta(days=40), price=500, quantity=9,
            origem="BLIZZARD", granularidade="HORARIA",
        )
    )
    db_session.commit()
    fonte_falsa.com_dias(9802, dias(10))

    resumo = _importar(db_session, [item], incremental=True)

    assert resumo.registros_importados == 10
