import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Base Model para todos os models da aplicação herdarem
Base = declarative_base()

def get_database_url() -> str:
    """Monta a URL de conexão baseada nas variáveis de ambiente."""
    user = os.getenv("DB_USER", "goblin")
    password = os.getenv("DB_PASS", "goblin_password")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "goblinledger")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

def ensure_unaccent_extension(engine) -> None:
    """
    CU03-C1 passo 2: a busca de itens desconsidera acentuação com a extensão `unaccent` do PostgreSQL.
    Idempotente. Será movida para a migração inicial do Alembic quando ele for introduzido.
    """
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    except ProgrammingError:
        logger.error(
            "Não foi possível criar a extensão 'unaccent' (permissão insuficiente?). "
            "A busca de itens (CU03) ficará indisponível até que um superusuário execute: CREATE EXTENSION unaccent;"
        )

def init_db():
    """
    Inicializa a engine, cria as tabelas caso não existam (Migration simplificada pura)
    e retorna o sessionmaker para produzir sessoes pro banco.
    """
    db_url = get_database_url()
    logger.info(f"Conectando ao banco de dados no host: {os.getenv('DB_HOST', 'localhost')}")
    
    try:
        engine = create_engine(db_url, echo=False)
        # Import local para criar as tabelas que herdam da Base
        from src.models.item_price import ItemPrice
        from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog
        from src.models.item import Item
        
        ensure_unaccent_extension(engine)

        # Cria as tabelas configuradas se elas não existirem no target DB
        Base.metadata.create_all(engine)
        logger.info("Tabelas do banco de dados verificadas/criadas com sucesso.")
        
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
