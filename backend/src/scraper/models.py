import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Integer, String, Text, UniqueConstraint
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import declarative_base
from src.repositories.database import Base
class ExecutionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

# CU10-C1 (RN16): granularidade de cada ponto de historical_item_prices.
GRANULARIDADE_DIARIA = "DIARIA"  # agregado diário da Undermine (00:00 UTC) ou dia inteiro
GRANULARIDADE_HORARIA = "HORARIA"  # snapshot horário (Undermine ou ciclo da Blizzard do CU09)

# CU10-C1: quem disparou a importação (scraper_execution_logs.triggered_by).
DISPARO_ADMIN = "ADMIN"
DISPARO_RECUPERACAO = "RECUPERACAO"  # regra de recuperação de 48 h do worker (CU09)

# CU10-C1: etapa em que a importação falhou (scraper_execution_logs.failure_stage).
FALHA_FONTE = "FONTE"  # FE1: fonte indisponível
FALHA_BANCO = "BANCO"  # FE2: gravação
FALHA_FORMATO = "FORMATO"  # FE3: arquivo que não decodifica
FALHA_INTERNA = "INTERNA"  # qualquer outro erro inesperado

class HistoricalItemPrice(Base):
    __tablename__ = "historical_item_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, index=True, nullable=False)
    region = Column(String(50), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    price = Column(BigInteger, nullable=False)
    quantity = Column(Integer, nullable=True)
    # CU09: 'UNDERMINE' (backfill dos .bin, diário) ou 'BLIZZARD' (ciclo horário; price = valor de mercado, RN06).
    origem = Column(String(10), nullable=False, default="UNDERMINE", server_default="UNDERMINE")
    # CU09-C2 passo 4 (RN12): volume do ciclo marcado como anômalo (injeção artificial de itens por bots).
    anomalia = Column(Boolean, nullable=False, default=False, server_default="false")
    # CU10 (RN16): período que o ponto representa. O CU11 não deve misturar as duas séries sem tratamento.
    granularidade = Column(String(10), nullable=False, default="DIARIA", server_default="DIARIA")

    __table_args__ = (
        UniqueConstraint('item_id', 'region', 'timestamp', name='uq_item_region_timestamp'),
    )

class ScraperExecutionLog(Base):
    __tablename__ = "scraper_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_start = Column(DateTime, nullable=False)
    execution_end = Column(DateTime, nullable=True)
    status = Column(Enum(ExecutionStatus), nullable=False)
    items_processed = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    # CU10-C1: pedido e resumo da importação (registros nulos = execuções anteriores ao CU10).
    triggered_by = Column(String(15), nullable=True)
    region = Column(String(50), nullable=True)  # reino conectado consultado (o mesmo valor de historical_item_prices.region)
    items_requested = Column(Integer, nullable=True)
    items_created = Column(Integer, nullable=True)  # CU10-C1-FA2
    items_without_data = Column(Integer, nullable=True)  # a fonte não tem arquivo do item
    items_failed = Column(Integer, nullable=True)  # falha de rede ou da fonte só nesse item (a importação seguiu)
    records_discarded = Column(Integer, nullable=True)
    records_duplicated = Column(Integer, nullable=True)
    failure_stage = Column(String(10), nullable=True)  # FONTE, BANCO, FORMATO ou INTERNA

# T004 Pydantic validation schemas
class UndermineItemPrice(BaseModel):
    item_id: int
    region: str
    timestamp: datetime
    price: int
    quantity: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
