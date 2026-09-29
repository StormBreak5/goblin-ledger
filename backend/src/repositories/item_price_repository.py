import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from src.models.item_price import ItemPrice
from src.models.api_models import WoWTokenResponse

logger = logging.getLogger(__name__)

class ItemPriceRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_price(self, item_id: int, region: str, token_response: WoWTokenResponse) -> ItemPrice:
        # Na inserção, guardamos o valor puro em int para o copper.
        new_record = ItemPrice(
            item_id=item_id,
            region=region,
            price_copper=token_response.price
        )
        
        try:
            self.session.add(new_record)
            self.session.commit()
            gold_val = token_response.price / 10000
            logger.info(f"Salvo preço no DB! Item: {item_id}, Regiao: {region}, Price (Gold): {gold_val}")
            
            return new_record
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erro ao salvar dado de preco do item {item_id}: {e}")
            raise

    def history(self, item_id: int, region: str, since: Optional[datetime] = None) -> list[ItemPrice]:
        """Série de preços do item (Ficha do WoW), do mais antigo para o mais novo. `since` (com fuso) limita a janela."""
        query = self.session.query(ItemPrice).filter(ItemPrice.item_id == item_id, ItemPrice.region == region)
        if since is not None:
            query = query.filter(ItemPrice.created_at >= since)
        return query.order_by(ItemPrice.created_at.asc()).all()

    def latest(self, item_id: int, region: str) -> Optional[ItemPrice]:
        """O preço mais recente do item (Ficha do WoW), ou None se ainda não houve coleta."""
        return (
            self.session.query(ItemPrice)
            .filter(ItemPrice.item_id == item_id, ItemPrice.region == region)
            .order_by(ItemPrice.created_at.desc())
            .first()
        )
