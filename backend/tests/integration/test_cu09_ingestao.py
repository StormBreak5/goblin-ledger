"""
Plano de testes do CU09 – Cadastrar Dados de Mercado (RF07 / RF10), cenários 01 a 03: um teste por fluxo do
documento do TC, mais a regra de recuperação da coleta (48 h) e o consumo dos dados. Rodam contra um PostgreSQL
temporário (ver tests/conftest.py); a API da Blizzard e o relógio são falsos.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from helpers_ingestao import (
    MERCADO_COMMODITIES,
    MERCADO_REINO,
    leilao_de_commodity,
    leilao_de_reino,
)
from src.models.item import Item
from src.models.mercado import CicloIngestao, EstadoMercado, Leilao
from src.repositories.mercado_repository import MercadoRepository
from src.scraper.models import ExecutionStatus, HistoricalItemPrice, ScraperExecutionLog
from src.services.api_client import ApiIndisponivelError
from src.services.ingestao_config import carregar_mercados
from src.services.item_service import ItemService
from src.services.rodada_de_ingestao import executar_rodada

MARGEM = timedelta(seconds=5)


def _pontos(db_session):
    return db_session.query(HistoricalItemPrice).filter(HistoricalItemPrice.origem == "BLIZZARD").order_by(
        HistoricalItemPrice.item_id, HistoricalItemPrice.timestamp
    ).all()


def _sem_fuso(momento: datetime) -> datetime:
    return momento.astimezone(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- CU09-C1: coletar dados de mercado

def test_cu09_c1_fluxo_principal_coleta_e_encaminha_payload(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    cliente_blizzard.payload_das_commodities = {"auctions": [leilao_de_commodity(2, 2001, 50, 20)]}

    resultado_reino = ingestao.executar(MERCADO_REINO)
    resultado_commodities = ingestao.executar(MERCADO_COMMODITIES)

    assert resultado_reino.status == resultado_commodities.status == "SUCESSO"
    assert cliente_blizzard.chamadas == ["auctions:us:3209", "commodities:us"]  # um endpoint para cada mercado
    ciclos = {ciclo.endpoint: ciclo for ciclo in db_session.query(CicloIngestao)}
    assert set(ciclos) == {"auctions:us:3209", "commodities:us"}
    ciclo = ciclos["auctions:us:3209"]
    assert (ciclo.origem, ciclo.status, ciclo.leiloes_coletados) == ("AGENDADO", "SUCESSO", 1)
    assert ciclo.iniciado_em == relogio() and ciclo.data_referencia == relogio()  # passo 6: data e hora da coleta


def test_cu09_c1_fa1_intervalo_minimo_nao_atingido(ingestao, cliente_blizzard, db_session, relogio):
    primeira = relogio()
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"

    relogio.avancar(minutes=59, seconds=59)
    resultado = ingestao.executar(MERCADO_REINO)

    assert resultado.status == "CANCELADO"
    assert resultado.proxima_permitida == primeira + timedelta(minutes=60)
    assert len(cliente_blizzard.chamadas) == 1  # a API nem foi consultada
    assert db_session.query(CicloIngestao).count() == 1  # e nenhum ciclo novo foi registrado

    relogio.avancar(seconds=1)  # completou os 60 minutos
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"
    assert len(cliente_blizzard.chamadas) == 2


def test_cu09_c1_fa2_reino_fora_do_dominio_geografico_rn11(caplog):
    with caplog.at_level(logging.WARNING, logger="src.services.ingestao_config"):
        mercados = carregar_mercados("us:3209, cn:77, eu:1305")

    assert [mercado.chave for mercado in mercados] == [
        "auctions:us:3209", "auctions:eu:1305", "commodities:us", "commodities:eu",
    ]  # o reino da região CN foi ignorado e os demais seguem
    assert "CU09-C1-FA2" in caplog.text and "cn:77" in caplog.text


def test_cu09_c1_fe1_falha_da_api_mantem_dados_e_sinaliza_desatualizado(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    primeira = relogio()
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"

    relogio.avancar(minutes=61)
    cliente_blizzard.erro = ApiIndisponivelError("A API não respondeu após 4 tentativas: HTTP 503")
    resultado = ingestao.executar(MERCADO_REINO)

    assert (resultado.status, resultado.etapa_da_falha) == ("FALHA", "COLETA")
    assert db_session.query(Leilao).one().data_ingestao == primeira  # os dados do ciclo anterior foram mantidos
    estado = db_session.query(EstadoMercado).one()
    assert estado.desatualizado is True and estado.ultima_falha_em == relogio()  # RN14
    ciclo_com_falha = db_session.query(CicloIngestao).filter(CicloIngestao.status == "FALHA").one()
    assert ciclo_com_falha.etapa_da_falha == "COLETA" and "503" in ciclo_com_falha.erro

    relogio.avancar(minutes=61)
    cliente_blizzard.erro = None
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"
    db_session.expire_all()
    assert db_session.query(EstadoMercado).one().desatualizado is False  # o próximo ciclo bem-sucedido limpa a bandeira


# ---------------------------------------------------------------- CU09-C1: ativação (regras de agendamento)

def _backfill_recente(db_session, relogio, horas_atras: int = 1) -> None:
    """O último backfill dos .bin terminou há pouco: não há lacuna de histórico a recompor."""
    concluido = _sem_fuso(relogio() - timedelta(hours=horas_atras))
    db_session.add(ScraperExecutionLog(execution_start=concluido, execution_end=concluido, status=ExecutionStatus.SUCCESS))
    db_session.commit()


def _rodar(db_session, cliente_blizzard, relogio, recuperacoes):
    return executar_rodada(
        db_session, cliente_blizzard, [MERCADO_REINO],
        lambda: recuperacoes.append(len(cliente_blizzard.chamadas)), relogio,
    )


def test_cu09_c1_ativacao_coleta_imediata_ao_iniciar_apos_uma_hora(db_session, cliente_blizzard, relogio):
    _backfill_recente(db_session, relogio)
    recuperacoes: list[int] = []
    _rodar(db_session, cliente_blizzard, relogio, recuperacoes)  # primeira coleta (nunca houve nenhuma)
    relogio.avancar(minutes=61)

    _rodar(db_session, cliente_blizzard, relogio, recuperacoes)  # o worker reinicia mais de uma hora depois

    assert len(cliente_blizzard.chamadas) == 2  # coletou na hora
    assert db_session.query(CicloIngestao).count() == 2


def test_cu09_c1_ativacao_agenda_para_ultimo_ciclo_mais_60_minutos(db_session, cliente_blizzard, relogio):
    _backfill_recente(db_session, relogio)
    recuperacoes: list[int] = []
    primeira = relogio()
    _rodar(db_session, cliente_blizzard, relogio, recuperacoes)
    relogio.avancar(minutes=20)

    proximo = _rodar(db_session, cliente_blizzard, relogio, recuperacoes)  # reinício antes de completar 1 hora

    assert len(cliente_blizzard.chamadas) == 1  # não coletou de novo
    assert proximo == primeira + timedelta(minutes=60) + MARGEM  # e agendou para o horário liberado pela RN05
    assert recuperacoes == []


def test_cu09_c1_ativacao_backfill_antes_do_ciclo_apos_48h(db_session, cliente_blizzard, relogio):
    _backfill_recente(db_session, relogio)
    recuperacoes: list[int] = []
    _rodar(db_session, cliente_blizzard, relogio, recuperacoes)
    relogio.avancar(hours=72)  # a aplicação ficou desligada por 3 dias

    proximo = _rodar(db_session, cliente_blizzard, relogio, recuperacoes)

    assert recuperacoes == [1]  # o backfill rodou quando só a primeira coleta tinha acontecido, ou seja, antes do ciclo
    assert len(cliente_blizzard.chamadas) == 2  # e o ciclo da Blizzard veio depois
    assert proximo == relogio() + timedelta(minutes=60) + MARGEM


def test_cu09_c1_ativacao_referencia_das_48h_e_a_ultima_coleta_de_qualquer_origem(db_session, cliente_blizzard, relogio):
    # Nenhum ciclo da Blizzard ainda, mas o último backfill terminou há 3 horas: não há lacuna a recompor.
    _backfill_recente(db_session, relogio, horas_atras=3)
    recuperacoes: list[int] = []

    _rodar(db_session, cliente_blizzard, relogio, recuperacoes)

    assert recuperacoes == []
    assert len(cliente_blizzard.chamadas) == 1  # coletou na hora: nunca houve requisição a esse endpoint
    # A referência é a coleta mais recente entre as duas origens.
    relogio.avancar(days=1)
    repositorio = MercadoRepository(db_session)
    assert repositorio.ultima_coleta() == relogio() - timedelta(days=1)  # o ciclo de agora há 1 dia, mais novo que o backfill


# ---------------------------------------------------------------- CU09-C2: sanitizar e padronizar

def test_cu09_c2_fluxo_principal_sanitiza_e_padroniza_em_cobre(ingestao, cliente_blizzard, db_session):
    cliente_blizzard.payload_do_reino = {"auctions": [
        leilao_de_reino(1, 1001, 30000, quantidade=3, bid=25000),  # 3 unidades por 3 ouro: 1 ouro cada
        leilao_de_reino(2, 1002, None, bid=500),  # só com lance, sem preço de compra
        {"id": 3, "item": {"id": 1003}, "quantity": "muitos", "buyout": 100},  # tipo incompatível
        {"id": 4, "quantity": 1, "buyout": 100},  # campo obrigatório ausente (item)
        {"id": 5, "item": {"id": 1005}, "quantity": 1, "buyout": -10},  # preço negativo
        {"id": True, "item": {"id": 1006}, "quantity": 1, "buyout": 10},  # booleano não é inteiro
        "registro inválido",
    ]}

    resultado = ingestao.executar(MERCADO_REINO)

    assert resultado.status == "SUCESSO"
    assert (resultado.leiloes_coletados, resultado.leiloes_descartados) == (2, 5)
    por_origem = {leilao.id_leilao_origem: leilao for leilao in db_session.query(Leilao)}
    assert set(por_origem) == {1, 2}  # só os válidos foram persistidos
    assert (por_origem[1].preco_bid, por_origem[1].preco_buyout, por_origem[1].preco_unitario) == (25000, 30000, 10000)
    assert (por_origem[2].preco_bid, por_origem[2].preco_buyout, por_origem[2].preco_unitario) == (500, None, None)


def test_cu09_c2_fa1_taxa_de_descarte_elevada_vai_para_o_log(ingestao, cliente_blizzard, db_session, caplog):
    validos = [leilao_de_reino(indice, 1001, 100 + indice) for indice in range(1, 8)]
    invalidos = [{"id": 100 + indice, "quantity": 1} for indice in range(3)]  # 30% de descarte, acima dos 5%
    cliente_blizzard.payload_do_reino = {"auctions": validos + invalidos}

    with caplog.at_level(logging.WARNING, logger="src.services.ingestao_service"):
        resultado = ingestao.executar(MERCADO_REINO)

    assert "CU09-C2-FA1" in caplog.text and "auditoria" in caplog.text  # o lote foi para o log
    assert resultado.status == "SUCESSO"  # e o processamento continua com os registros válidos
    assert db_session.query(Leilao).count() == 7


def test_cu09_c2_fe1_payload_fora_do_formato_descarta_tudo(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    primeira = relogio()
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"
    relogio.avancar(minutes=61)
    cliente_blizzard.payload_do_reino = {"endpoint_novo": [{"id": 9}]}  # a API mudou de formato

    resultado = ingestao.executar(MERCADO_REINO)

    assert (resultado.status, resultado.etapa_da_falha) == ("FALHA", "SANITIZACAO")
    leiloes = db_session.query(Leilao).all()
    assert [(leilao.id_leilao_origem, leilao.data_ingestao) for leilao in leiloes] == [(1, primeira)]  # nada novo
    assert len(_pontos(db_session)) == 1
    assert db_session.query(EstadoMercado).one().desatualizado is True


def test_cu09_c2_anomalia_de_volume_rn12(ingestao, cliente_blizzard, db_session, relogio):
    agora_sem_fuso = _sem_fuso(relogio())
    # 30 pontos de 10 unidades nos últimos dias: base de comparação suficiente (mínimo de 24) para o item 1001.
    for horas in range(1, 31):
        db_session.add(HistoricalItemPrice(
            item_id=1001, region="3209", timestamp=agora_sem_fuso - timedelta(hours=horas), price=100, quantity=10,
            origem="BLIZZARD",
        ))
    # O item 1002 tem só 3 pontos anteriores: sem base para julgar.
    for horas in range(1, 4):
        db_session.add(HistoricalItemPrice(
            item_id=1002, region="3209", timestamp=agora_sem_fuso - timedelta(hours=horas), price=100, quantity=10,
            origem="BLIZZARD",
        ))
    db_session.commit()
    cliente_blizzard.payload_do_reino = {"auctions": [
        leilao_de_reino(1, 1001, 100, quantidade=5000),  # 500x a mediana: injeção artificial
        leilao_de_reino(2, 1002, 100, quantidade=5000),  # mesmo volume, mas sem histórico suficiente
        leilao_de_reino(3, 1003, 100, quantidade=5),  # volume normal
    ]}

    resultado = ingestao.executar(MERCADO_REINO)

    marcados = {ponto.item_id: ponto.anomalia for ponto in _pontos(db_session) if ponto.timestamp == agora_sem_fuso}
    assert marcados == {1001: True, 1002: False, 1003: False}
    assert resultado.itens_anomalos == 1
    assert db_session.query(CicloIngestao).one().itens_anomalos == 1


# ---------------------------------------------------------------- CU09-C3: consolidar e persistir

def test_cu09_c3_fluxo_principal_persiste_classifica_e_calcula_valor_de_mercado(
    ingestao, cliente_blizzard, db_session, relogio, add_item
):
    add_item(1001, "Item de teste")
    inicio = relogio()
    cliente_blizzard.payload_do_reino = {"auctions": [
        leilao_de_reino(1, 1001, 100),  # 1 unidade a 100
        leilao_de_reino(2, 1001, 400, quantidade=2),  # 2 unidades a 200
        leilao_de_reino(3, 1001, 300),  # 1 unidade a 300
        leilao_de_reino(4, 1001, 2400, quantidade=6),  # 6 unidades a 400
        leilao_de_reino(5, 2002, 900),  # este some do próximo snapshot
    ]}
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"

    # O item 1001 tem 10 unidades: o 1º quartil ponderado (25% = 2,5 unidades) cai em 200, e não no mínimo (100).
    ponto = _pontos(db_session)[0]
    assert (ponto.item_id, ponto.region, ponto.price, ponto.quantity, ponto.origem) == (1001, "3209", 200, 10, "BLIZZARD")
    assert ponto.timestamp == _sem_fuso(inicio) and ponto.anomalia is False
    estado = db_session.query(EstadoMercado).one()
    assert estado.ultima_atualizacao_em == inicio and estado.desatualizado is False  # RN09

    # 3 dias depois: o leilão 5 não aparece mais; os demais continuam.
    relogio.avancar(days=3)
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100), leilao_de_reino(6, 1001, 150)]}
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"

    situacoes = {leilao.id_leilao_origem: leilao.situacao for leilao in db_session.query(Leilao)}
    # RN04: sem atualização há mais de 48 h vira Expirado/Vendido e continua no banco (dentro da retenção).
    assert situacoes == {1: "ATIVO", 2: "EXPIRADO_VENDIDO", 3: "EXPIRADO_VENDIDO", 4: "EXPIRADO_VENDIDO",
                         5: "EXPIRADO_VENDIDO", 6: "ATIVO"}
    # O histórico ganhou um ponto novo (o do item 1001) e os antigos (itens 1001 e 2002) permanecem.
    assert [(ponto.item_id, ponto.price) for ponto in _pontos(db_session)] == [(1001, 200), (1001, 100), (2002, 900)]
    # Só os leilões do último ciclo contam como atuais: o 5, que sumiu do snapshot, e os expirados ficam de fora.
    assert sorted(MercadoRepository(db_session).leiloes_do_ultimo_ciclo(1001)) == [(100, 1), (150, 1)]
    assert MercadoRepository(db_session).leiloes_do_ultimo_ciclo(2002) == []


def test_cu09_c3_repetir_o_mesmo_snapshot_nao_duplica_o_historico(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    cliente_blizzard.last_modified = relogio()  # a Blizzard ainda não publicou um snapshot novo
    ingestao.executar(MERCADO_REINO)

    relogio.avancar(minutes=61)
    ingestao.executar(MERCADO_REINO)

    assert len(_pontos(db_session)) == 1 and db_session.query(Leilao).count() == 1
    assert db_session.query(CicloIngestao).count() == 2


def test_cu09_c3_retencao_remove_expirados_antigos_e_preserva_o_historico(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    ingestao.executar(MERCADO_REINO)

    relogio.avancar(days=10)  # o leilão 1 expirou há muito mais que a retenção de 7 dias
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(2, 1001, 120)]}
    ingestao.executar(MERCADO_REINO)

    assert [leilao.id_leilao_origem for leilao in db_session.query(Leilao)] == [2]
    assert len(_pontos(db_session)) == 2  # o resumo horário é o histórico de longo prazo: nada dele saiu


def test_cu09_c3_fa1_item_nao_cadastrado_e_criado(ingestao, cliente_blizzard, db_session, add_item):
    add_item(1001, "Item conhecido", "https://icone.exemplo/1001.jpg")
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100), leilao_de_reino(2, 424242, 500)]}

    resultado = ingestao.executar(MERCADO_REINO)

    assert resultado.itens_cadastrados == 1
    novo = db_session.query(Item).filter(Item.external_item_id == "424242").one()
    assert (novo.game, novo.name, novo.icon_url) == ("wow", "Item 424242", None)  # nome provisório
    conhecido = db_session.query(Item).filter(Item.external_item_id == "1001").one()
    assert (conhecido.name, conhecido.icon_url) == ("Item conhecido", "https://icone.exemplo/1001.jpg")  # intacto


def test_cu09_c3_fe1_falha_de_banco_desfaz_e_sinaliza(ingestao, cliente_blizzard, db_session, relogio, mocker):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 100)]}
    primeira = relogio()
    assert ingestao.executar(MERCADO_REINO).status == "SUCESSO"
    relogio.avancar(minutes=61)
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 1001, 90), leilao_de_reino(7, 2002, 700)]}
    # O banco cai no passo 5, depois de os leilões já terem sido gravados na transação: tudo deve ser desfeito.
    mocker.patch.object(
        MercadoRepository, "registrar_atualizacao", side_effect=OperationalError("UPDATE", {}, Exception("connection lost"))
    )

    resultado = ingestao.executar(MERCADO_REINO)

    mocker.stopall()
    db_session.expire_all()
    assert (resultado.status, resultado.etapa_da_falha) == ("FALHA", "CONSOLIDACAO")
    leiloes = {leilao.id_leilao_origem: leilao for leilao in db_session.query(Leilao)}
    assert set(leiloes) == {1} and leiloes[1].preco_unitario == 100 and leiloes[1].data_ingestao == primeira
    assert len(_pontos(db_session)) == 1  # sem ponto novo no histórico
    estado = db_session.query(EstadoMercado).one()
    assert estado.desatualizado is True and estado.ultima_atualizacao_em == primeira  # dados do ciclo anterior mantidos
    assert db_session.query(CicloIngestao).filter(CicloIngestao.status == "FALHA").one().etapa_da_falha == "CONSOLIDACAO"


def test_cu09_consumo_get_current_auctions_le_do_banco(ingestao, cliente_blizzard, db_session, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [
        leilao_de_reino(1, 1001, 100), leilao_de_reino(2, 1001, 400, quantidade=2),
        leilao_de_reino(3, 1001, 300), leilao_de_reino(4, 1001, 2400, quantidade=6),
    ]}
    cliente_blizzard.payload_das_commodities = {"auctions": [leilao_de_commodity(10, 1001, 50, 90)]}
    ingestao.executar(MERCADO_REINO)
    ingestao.executar(MERCADO_COMMODITIES)
    servico = ItemService(db_session)

    atuais = servico.get_current_auctions(1001)
    sem_leiloes = servico.get_current_auctions(9999)

    assert atuais == {"min_price": 50, "total_quantity": 100, "market_value": 50}  # o item também é vendido como commodity
    assert sem_leiloes == {"min_price": 0, "total_quantity": 0, "market_value": None}


def test_cu09_c3_fa1_itens_novos_disparam_o_preenchimento_de_nomes_e_icones(db_session, cliente_blizzard, relogio):
    cliente_blizzard.payload_do_reino = {"auctions": [leilao_de_reino(1, 424242, 500)]}
    chamadas: list[str] = []
    _backfill_recente(db_session, relogio)

    executar_rodada(db_session, cliente_blizzard, [MERCADO_REINO], lambda: None, relogio, lambda: chamadas.append("preencher"))
    relogio.avancar(minutes=61)  # nenhum item novo neste ciclo: nada a preencher
    executar_rodada(db_session, cliente_blizzard, [MERCADO_REINO], lambda: None, relogio, lambda: chamadas.append("preencher"))

    assert chamadas == ["preencher"]
