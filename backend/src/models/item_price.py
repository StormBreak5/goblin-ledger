import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from src.repositories.database import Base

# A Ficha do WoW não tem leilões: o preço vem da API dedicada (a cada 15 min, `job_fetch_wow_token_price`) e fica em
# `item_prices`, e não em `historical_item_prices` nem em `leilao`. As telas do item leem daqui quando o item é a Ficha.
WOW_TOKEN_ID = 122284
REGIAO_DA_FICHA = "us"


class ItemPrice(Base):
    __tablename__ = "item_prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(Integer, nullable=False)
    price_copper = Column(BigInteger, nullable=False)
    region = Column(String(5), nullable=False, default="us")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Definindo composite index explicitamente para perfomance no timeseries
    __table_args__ = (
        Index('idx_item_region_created_at', 'item_id', 'region', 'created_at'),
    )

    def __repr__(self):
        gold = self.price_copper / 10000 if self.price_copper else 0
        return f"<ItemPrice(item_id={self.item_id}, region='{self.region}', gold={gold}, created_at={self.created_at})>"
