import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, ColumnElement, String, Boolean, DateTime, Index, case, cast, func, literal
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



def _como_objeto(valor: ColumnElement[Any]) -> ColumnElement[Any]:
    """O valor como objeto JSONB; NULL, `null` e qualquer outro tipo JSON valem `{}` (no PostgreSQL, `objeto || null`
    vira um array). O cast explícito evita que um parâmetro sem tipo seja concatenado como texto."""
    valor = cast(valor, JSONB)
    return case((func.jsonb_typeof(valor) == "object", valor), else_=cast(literal({}, JSONB), JSONB))


def mesclar_metadata(base: ColumnElement[Any], por_cima: ColumnElement[Any]) -> ColumnElement[Any]:
    """`base || por_cima` em JSONB: as chaves de `por_cima` entram ou trocam de valor e as demais ficam como estão. Quem
    grava em `items.metadata_info` (sincronização diária, ETag e origem do CU10-C1, atributos do item) mescla, nunca
    substitui o JSON inteiro."""
    return _como_objeto(base).op("||", return_type=JSONB)(_como_objeto(por_cima))
