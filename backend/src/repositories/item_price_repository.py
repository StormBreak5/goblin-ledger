import logging
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.models.item_price import ItemPrice
from src.models.api_models import WoWTokenResponse

logger = logging.getLogger(__name__)

LIMITE_EM_SEGUNDOS = 10**11  # acima disso o instante da Blizzard está em milissegundos


def instante_da_blizzard(marca: int) -> datetime:
    """`last_updated_timestamp` da API da Ficha (milissegundos; segundos também são aceitos) como instante UTC."""
    segundos = marca / 1000 if marca > LIMITE_EM_SEGUNDOS else marca
    return datetime.fromtimestamp(segundos, tz=timezone.utc)


class ItemPriceRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_price(self, item_id: int, region: str, token_response: WoWTokenResponse) -> Optional[ItemPrice]:
        # Na inserção, guardamos o valor puro em int para o copper. O instante do ponto é o do preço na Blizzard (que só o
        # atualiza a cada 20 min), e não o da coleta: a leitura não se repete a cada consulta de 15 min e a série segue a
        # do histórico importado da Undermine.
        new_record = ItemPrice(
            item_id=item_id,
            region=region,
            price_copper=token_response.price,
            created_at=instante_da_blizzard(token_response.last_updated_timestamp),
        )

        try:
            self.session.add(new_record)
            self.session.commit()
            gold_val = token_response.price / 10000
            logger.info(f"Salvo preço no DB! Item: {item_id}, Regiao: {region}, Price (Gold): {gold_val}")

            return new_record
        except IntegrityError:
            self.session.rollback()
            logger.info(f"Preço da Ficha ({item_id}, {region}) já registrado para o instante {new_record.created_at}; ignorado.")
            return None
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erro ao salvar dado de preco do item {item_id}: {e}")
            raise

    def importar_historico(self, item_id: int, region: str, pontos: Sequence[tuple[datetime, int]]) -> int:
        """Grava os pontos (instante UTC, preço em Cobre) que ainda não existem e devolve quantos entraram. Não confirma."""
        if not pontos:
            return 0
        linhas = [{"item_id": item_id, "region": region, "price_copper": preco, "created_at": instante} for instante, preco in pontos]
        resultado = self.session.execute(
            insert(ItemPrice).values(linhas).on_conflict_do_nothing(constraint="uq_item_prices_item_region_created")
        )
        return resultado.rowcount

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
