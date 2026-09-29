import os
import uuid
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

# Antes de qualquer import do código: hash barato e segredo fixo só nos testes.
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("JWT_SECRET", "segredo-somente-para-testes-com-mais-de-32-bytes")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.controllers import item_controller
from src.models.cobertura import AptidaoTreinamento
from src.models.evento import EventoJogo, ExtracaoEvento
from src.models.item import Item
from src.models.mercado import CicloIngestao, EstadoMercado, Leilao, Reino
from src.models.usuario import TentativaLogin, Usuario
from src.repositories.database import run_migrations
from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog

# Padrões públicos do docker-compose/.env.example (banco em localhost:5435). Sobrescreva com TEST_DATABASE_URL.
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg2://goblin:goblin_password@localhost:5435/goblinledger"


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


@pytest.fixture
def make_auth_client() -> Callable[..., TestClient]:
    """
    TestClient das rotas de usuário, autenticação, mercado e dados passados (CU01/CU02/CU09/CU10) com as dependências
    substituídas: `abridor` (como a sessão do banco é aberta), `relogio`, `email_service`, `cliente_blizzard` e
    `baixar_pagina` (leitura das páginas de referência dos eventos).
    """
    def _make(
        abridor: Callable, relogio: Optional[Callable] = None, email_service=None, cliente_blizzard=None, baixar_pagina=None
    ) -> TestClient:
        from src.controllers import (
            admin_cobertura_controller,
            admin_eventos_controller,
            admin_historico_controller,
            auth_controller,
            deps,
            mercado_controller,
            usuario_controller,
        )

        app = FastAPI()
        app.include_router(usuario_controller.router, prefix="/api")
        app.include_router(auth_controller.router, prefix="/api")
        app.include_router(mercado_controller.router, prefix="/api")
        app.include_router(admin_historico_controller.router, prefix="/api")
        app.include_router(admin_eventos_controller.router, prefix="/api")
        app.include_router(admin_cobertura_controller.router, prefix="/api")
        app.dependency_overrides[deps.get_abridor_de_sessao] = lambda: abridor
        app.dependency_overrides[deps.get_preenchedor_de_itens] = lambda: (lambda: None)  # nunca chama a Blizzard
        if relogio is not None:
            app.dependency_overrides[deps.get_relogio] = lambda: relogio
        if email_service is not None:
            app.dependency_overrides[deps.get_email_service] = lambda: email_service
        if cliente_blizzard is not None:
            app.dependency_overrides[deps.get_fabrica_de_cliente_blizzard] = lambda: (lambda: cliente_blizzard)
        if baixar_pagina is not None:
            app.dependency_overrides[deps.get_baixador_de_pagina] = lambda: baixar_pagina
        return TestClient(app, raise_server_exceptions=False)

    return _make


@contextmanager
def banco_temporario() -> Iterator[Engine]:
    """
    Cria um banco PostgreSQL vazio e exclusivo do teste (`unaccent`, JSONB, UUID e ON CONFLICT exigem PostgreSQL)
    e o descarta ao final. O banco real do projeto nunca é lido nem alterado.
    """
    server_url: URL = make_url(os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
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
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    """Banco temporário com o esquema criado pelas migrações, como em produção."""
    with banco_temporario() as engine:
        run_migrations(engine)
        yield engine


@pytest.fixture
def banco_vazio() -> Iterator[Engine]:
    """Banco temporário sem nenhuma tabela, para testar as próprias migrações."""
    with banco_temporario() as engine:
        yield engine


@pytest.fixture
def db_session(pg_engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=pg_engine)()
    yield session
    session.rollback()
    session.query(HistoricalItemPrice).delete()
    session.query(ScraperExecutionLog).delete()
    session.query(Item).delete()
    session.query(TentativaLogin).delete()
    session.query(Usuario).delete()  # sessões e tokens saem por ON DELETE CASCADE
    session.query(Leilao).delete()
    session.query(EstadoMercado).delete()
    session.query(CicloIngestao).delete()
    session.query(Reino).delete()
    session.query(EventoJogo).delete()
    session.query(ExtracaoEvento).delete()
    session.query(AptidaoTreinamento).delete()
    session.commit()
    session.close()


@pytest.fixture
def fonte_falsa(mocker):
    """Undermine Exchange falsa (CU10-C1): substitui o download dos arquivos de cada item."""
    from helpers_historico import FonteFalsa
    from src.scraper import backfill

    fonte = FonteFalsa()
    mocker.patch.object(backfill, "fetch_item_history", fonte.buscar)
    return fonte


@pytest.fixture
def add_item(db_session: Session) -> Callable[..., Item]:
    def _add(external_item_id: int, name: str, icon_url: Optional[str] = None) -> Item:
        item = Item(game="wow", external_item_id=str(external_item_id), name=name, icon_url=icon_url)
        db_session.add(item)
        db_session.commit()
        return item

    return _add
