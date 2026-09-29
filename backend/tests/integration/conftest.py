from datetime import datetime
from typing import Callable

import pytest
from sqlalchemy.orm import Session

from src.scraper.models import HistoricalItemPrice
from src.services.item_service import ItemService


@pytest.fixture
def client(make_client, db_session: Session):
    """TestClient das rotas de itens usando o serviço real sobre o PostgreSQL de teste (ver tests/conftest.py)."""
    return make_client(lambda: ItemService(db_session))


@pytest.fixture
def add_history(db_session: Session) -> Callable[..., None]:
    def _add(item_id: int, timestamp: datetime, region: str = "3209", price: int = 100000, quantity: int = 10) -> None:
        db_session.add(
            HistoricalItemPrice(item_id=item_id, region=region, timestamp=timestamp, price=price, quantity=quantity)
        )
        db_session.commit()

    return _add
