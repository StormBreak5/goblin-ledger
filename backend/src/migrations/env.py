from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from src.repositories.database import Base, get_database_url
# Importa os modelos para que suas tabelas existam em Base.metadata (usado pelo --autogenerate e pelo teste de deriva).
from src.models.item import Item  # noqa: F401
from src.models.item_price import ItemPrice  # noqa: F401
from src.models.mercado import CicloIngestao, EstadoMercado, Leilao, Reino  # noqa: F401
from src.models.usuario import Sessao, TentativaLogin, TokenRecuperacao, Usuario  # noqa: F401
from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# API e worker sobem juntos e ambos aplicam as migrações: a trava faz um esperar o outro (liberada ao fim da transação).
MIGRATION_LOCK_ID = 7301202609


def _run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
        context.run_migrations()


def run_migrations_online() -> None:
    # Execução programática (init_db e testes) entrega a conexão pronta em config.attributes["connection"].
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_migrations(connection)
        return

    engine = create_engine(config.get_main_option("sqlalchemy.url") or get_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        _run_migrations(connection)


if context.is_offline_mode():
    raise RuntimeError("Migrações offline não são suportadas: use `alembic upgrade head` com acesso ao banco.")

run_migrations_online()
