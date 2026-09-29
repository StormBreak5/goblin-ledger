from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.orm import Session

from src.scraper.models import HistoricalItemPrice
from src.services.erros import EmailIndisponivelError
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


class RelogioFalso:
    """Relógio controlável: testa bloqueio de 15 min, link de 10 min e sessão de 24 h sem esperar."""

    def __init__(self) -> None:
        self.agora = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **duracao) -> None:
        self.agora += timedelta(**duracao)


class EmailFalso:
    """Substitui o envio por SMTP: guarda as mensagens ou simula o serviço de e-mail fora do ar."""

    def __init__(self) -> None:
        self.enviados: list[dict] = []
        self.indisponivel = False

    def enviar_link_de_recuperacao(self, destinatario: str, link: str, validade_minutos: int) -> None:
        if self.indisponivel:
            raise EmailIndisponivelError("SMTP fora do ar")
        self.enviados.append({"para": destinatario, "link": link, "validade_minutos": validade_minutos})

    def token_do_ultimo_link(self) -> str:
        return parse_qs(urlparse(self.enviados[-1]["link"]).query)["token"][0]


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso()


@pytest.fixture
def email_falso() -> EmailFalso:
    return EmailFalso()


def abridor_de_sessao_para(session: Session) -> Callable:
    """Entrega sempre a sessão do teste (sem fechá-la), no formato esperado por `get_abridor_de_sessao`."""
    @contextmanager
    def abrir():
        yield session

    return abrir


@pytest.fixture
def auth_client(make_auth_client, db_session: Session, relogio: RelogioFalso, email_falso: EmailFalso):
    """TestClient dos CU01/CU02 sobre o PostgreSQL de teste, com relógio e e-mail falsos."""
    return make_auth_client(abridor_de_sessao_para(db_session), relogio, email_falso)


@pytest.fixture
def cliente_blizzard(relogio):
    from helpers_ingestao import ClienteBlizzardFalso

    return ClienteBlizzardFalso(relogio)


@pytest.fixture
def admin_client(make_auth_client, db_session, relogio, email_falso, cliente_blizzard):
    """TestClient com as rotas de mercado (CU09-C4), usando a API da Blizzard falsa."""
    return make_auth_client(abridor_de_sessao_para(db_session), relogio, email_falso, cliente_blizzard)


@pytest.fixture
def ingestao(db_session, cliente_blizzard, relogio):
    """IngestaoService (CU09) sobre o PostgreSQL de teste, com a API da Blizzard e o relógio falsos."""
    from src.services.ingestao_service import IngestaoService

    return IngestaoService(db_session, cliente_blizzard, relogio)
