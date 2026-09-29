import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Enum, Integer, String, Text, UniqueConstraint
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import declarative_base
from src.repositories.database import Base
class ExecutionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class HistoricalItemPrice(Base):
    __tablename__ = "historical_item_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, index=True, nullable=False)
    region = Column(String(50), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    price = Column(BigInteger, nullable=False)
    quantity = Column(Integer, nullable=True)

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

# T004 Pydantic validation schemas
class UndermineItemPrice(BaseModel):
    item_id: int
    region: str
    timestamp: datetime
    price: int
    quantity: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
