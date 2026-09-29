"""
CU04 (verificação) – a Ficha do WoW não tem leilões: o preço vem de `item_prices` (coletado a cada 15 min). A tela do item
lia só `historical_item_prices` e `leilao`, então o preço atual e o histórico da Ficha nunca apareciam.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.controllers import item_controller
from src.models.item_price import ItemPrice
from src.scraper.models import HistoricalItemPrice


@pytest.fixture
def cliente(db_session):
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    app.dependency_overrides[item_controller.get_db] = lambda: db_session  # estas rotas não passam por get_item_service
    yield TestClient(app, raise_server_exceptions=False)
    db_session.query(ItemPrice).delete()
    db_session.commit()


def _preco(momento: datetime, cobre: int, item_id: int = 122284, regiao: str = "us") -> ItemPrice:
    return ItemPrice(item_id=item_id, region=regiao, price_copper=cobre, created_at=momento)


def test_cu04_historico_da_ficha_vem_de_item_prices_em_cobre_e_utc(cliente, db_session):
    agora = datetime.now(timezone.utc).replace(microsecond=0)
    db_session.add_all([
        _preco(agora - timedelta(days=30), 2_600_000_000),  # fora da janela de 14 dias
        _preco(agora - timedelta(hours=3), 2_850_000_000),
        _preco(agora - timedelta(minutes=15), 2_868_980_000),
        _preco(agora, 2_900_000_000, regiao="eu"),  # outra região: não entra
    ])
    db_session.commit()

    resposta = cliente.get("/api/items/122284/history?window=14D")

    assert resposta.status_code == 200
    antigo, novo = resposta.json()
    assert (antigo["price"], novo["price"]) == (2_850_000_000, 2_868_980_000)  # cobre (RN01): o gráfico divide por 10.000
    assert novo["timestamp"].endswith("+00:00") and datetime.fromisoformat(novo["timestamp"]) == agora - timedelta(minutes=15)
    assert (novo["quantity"], novo["granularity"]) == (None, "HORARIA")  # sem volume; é um instante, e não um dia inteiro
    assert len(cliente.get("/api/items/122284/history?window=ALL").json()) == 3


def test_cu04_preco_atual_da_ficha_e_o_da_ultima_coleta_sem_contagem_de_leiloes(cliente, db_session):
    agora = datetime.now(timezone.utc)
    db_session.add_all([_preco(agora - timedelta(hours=1), 2_800_000_000), _preco(agora, 2_868_980_000)])
    db_session.commit()

    resposta = cliente.get("/api/items/122284/current-auctions")

    assert resposta.status_code == 200
    assert resposta.json() == {"min_price": 2_868_980_000, "total_quantity": None, "market_value": 2_868_980_000}


def test_cu04_ficha_sem_nenhuma_coleta_ainda_devolve_vazio(cliente):
    assert cliente.get("/api/items/122284/history").json() == []
    assert cliente.get("/api/items/122284/current-auctions").json() == {"min_price": 0, "total_quantity": None, "market_value": None}


def test_cu04_os_demais_itens_continuam_lendo_o_historico_de_leiloes(cliente, db_session):
    agora = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    db_session.add(HistoricalItemPrice(item_id=39354, region="3209", timestamp=agora, price=12_490, quantity=8))
    db_session.add(_preco(datetime.now(timezone.utc), 2_868_980_000, item_id=39354))  # item_prices não vale para outros itens
    db_session.commit()

    [ponto] = cliente.get("/api/items/39354/history").json()
    atual = cliente.get("/api/items/39354/current-auctions").json()

    assert (ponto["price"], ponto["quantity"]) == (12_490, 8)
    assert atual == {"min_price": 0, "total_quantity": 0, "market_value": None}  # sem leilões no último ciclo
    db_session.query(HistoricalItemPrice).delete()
    db_session.commit()
