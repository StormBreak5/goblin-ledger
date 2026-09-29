import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Base Model para todos os models da aplicação herdarem
Base = declarative_base()

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")

def get_database_url() -> str:
    """Monta a URL de conexão baseada nas variáveis de ambiente."""
    user = os.getenv("DB_USER", "goblin")
    password = os.getenv("DB_PASS", "goblin_password")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "goblinledger")

    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

def run_migrations(engine) -> None:
    """
    Aplica as migrações do Alembic (src/migrations) até a mais recente. Idempotente e seguro com API e worker
    subindo ao mesmo tempo (o env.py usa uma trava do PostgreSQL). A migração 0001 cria a extensão `unaccent`
    exigida pela busca de itens (CU03-C1 passo 2).
    """
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", MIGRATIONS_DIR)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

def init_db():
    """
    Inicializa a engine, aplica as migrações do Alembic
    e retorna o sessionmaker para produzir sessoes pro banco.
    """
    db_url = get_database_url()
    logger.info(f"Conectando ao banco de dados no host: {os.getenv('DB_HOST', 'localhost')}")

    try:
        engine = create_engine(db_url, echo=False)

        run_migrations(engine)
        logger.info("Migrações do banco de dados aplicadas com sucesso.")

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal
    except Exception as e:
        logger.error(f"Erro fatal ao conectar ou inicializar banco de dados: {e}")
        raise

# Utilizado globalmente na aplicacao injetado
SessionLocal = None

def get_session():
    """Helper para obter a sessao. Lembre de fechar no final do escopo."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = init_db()
    return SessionLocal()
