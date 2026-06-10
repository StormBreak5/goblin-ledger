import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.repositories.database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game = Column(String(50), nullable=False, index=True) # e.g., 'wow', 'ffxiv'
    external_item_id = Column(String(255), nullable=False, index=True) # e.g., '122284'
    name = Column(String(255), nullable=False)
    icon_url = Column(String(255), nullable=True)
    metadata_info = Column(JSONB, nullable=True, default=dict) # e.g., {"expansion_id": 11, "item_class": "Trade Goods"}
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_items_game_external_id', 'game', 'external_item_id', unique=True),
    )

    def __repr__(self):
        return f"<Item(game='{self.game}', external_item_id='{self.external_item_id}', name='{self.name}')>"
