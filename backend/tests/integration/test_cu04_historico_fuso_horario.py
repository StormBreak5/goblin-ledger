"""
CU04 (verificação) – o histórico do item devolve o horário sem ambiguidade de fuso: o banco guarda UTC sem fuso e a API
marca o instante como UTC ("+00:00"), para que o navegador o converta para o fuso de quem vê (GMT-3 no Brasil). Sem a
marca, o JavaScript lê "2026-09-29T11:30:00" como horário local e mostra 3 horas a mais.
"""
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.controllers import item_controller
from src.scraper.models import HistoricalItemPrice


def _ponto(item_id: int, momento: datetime, granularidade: str, price: int = 1000):
    return HistoricalItemPrice(
        item_id=item_id, region="3209", timestamp=momento, price=price, quantity=5,
        origem="UNDERMINE" if granularidade == "DIARIA" else "BLIZZARD", granularidade=granularidade,
    )


def test_cu04_historico_devolve_o_instante_em_utc_com_o_fuso_explicito_e_a_granularidade(db_session):
    app = FastAPI()
    app.include_router(item_controller.router, prefix="/api")
    app.dependency_overrides[item_controller.get_db] = lambda: db_session  # o histórico não passa por get_item_service
    client = TestClient(app, raise_server_exceptions=False)
    agora = datetime.now(timezone.utc).replace(tzinfo=None, minute=30, second=0, microsecond=0)
    dia = agora.replace(hour=0, minute=0) - timedelta(days=1)
    db_session.add_all([_ponto(7001, dia, "DIARIA"), _ponto(7001, agora - timedelta(hours=2), "HORARIA", 1200)])
    db_session.commit()

    resposta = client.get("/api/items/7001/history?window=7D")

    assert resposta.status_code == 200
    diario, horario = resposta.json()
    assert diario["timestamp"].endswith("+00:00") and horario["timestamp"].endswith("+00:00")
    assert datetime.fromisoformat(horario["timestamp"]) == (agora - timedelta(hours=2)).replace(tzinfo=timezone.utc)
    assert datetime.fromisoformat(horario["timestamp"]).astimezone(timezone(timedelta(hours=-3))).hour == (agora.hour - 2 - 3) % 24
    assert (diario["granularity"], horario["granularity"]) == ("DIARIA", "HORARIA")
    assert (horario["price"], horario["quantity"]) == (1200, 5)
