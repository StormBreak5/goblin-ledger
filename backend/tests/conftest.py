import os
import uuid
from typing import Callable, Iterator, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.controllers import item_controller
from src.models.item import Item
from src.repositories.database import Base, ensure_unaccent_extension
from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog

# Padrões públicos do docker-compose/.env.example (banco em localhost:5435). Sobrescreva com TEST_DATABASE_URL.
DEFAULT_TEST_DATABASE_URL = "postgresql://goblin:goblin_password@localhost:5435/goblinledger"


@pytest.fixture
def make_client() -> Callable[[Optional[Callable]], TestClient]:
    """
    Cria um TestClient somente com as rotas de itens (sem `src.main`, que conecta ao banco ao ser importado).
    `service_factory` substitui a dependência `get_item_service`; com None, a dependência real é usada.
    """
    def _make(service_factory: Optional[Callable] = None) -> TestClient:
        app = FastAPI()
        app.include_router(item_controller.router, prefix="/api")
        if service_factory is not None:
            app.dependency_overrides[item_controller.get_item_service] = service_factory
        return TestClient(app, raise_server_exceptions=False)

    return _make


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    """
    Engine de um banco PostgreSQL temporário e exclusivo dos testes (`unaccent`, JSONB, UUID e ON CONFLICT exigem
    PostgreSQL). O banco real do projeto nunca é lido nem alterado: cria-se outro banco, descartado ao final.
    """
    server_url = make_url(os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
    admin_engine = create_engine(server_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    test_db_name = f"goblinledger_test_{uuid.uuid4().hex[:8]}"

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    except (OperationalError, SQLAlchemyError) as exc:
        admin_engine.dispose()
        reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
        pytest.skip(
            f"PostgreSQL de teste indisponível em {server_url.host}:{server_url.port} "
            f"(suba o Docker do projeto ou defina TEST_DATABASE_URL): {reason}"
        )

    engine = create_engine(server_url.set(database=test_db_name))
    try:
        ensure_unaccent_extension(engine)
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture
def db_session(pg_engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=pg_engine)()
    yield session
    session.rollback()
    session.query(HistoricalItemPrice).delete()
    session.query(ScraperExecutionLog).delete()
    session.query(Item).delete()
    session.commit()
    session.close()


@pytest.fixture
def add_item(db_session: Session) -> Callable[..., Item]:
    def _add(external_item_id: int, name: str, icon_url: Optional[str] = None) -> Item:
        item = Item(game="wow", external_item_id=str(external_item_id), name=name, icon_url=icon_url)
        db_session.add(item)
        db_session.commit()
        return item

    return _add
