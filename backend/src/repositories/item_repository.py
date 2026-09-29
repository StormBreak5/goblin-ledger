from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.item import Item
from src.scraper.models import HistoricalItemPrice

LIKE_ESCAPE = "\\"


def escape_like(term: str) -> str:
    """CU03-C1 passo 3: neutraliza os curingas do LIKE para que o termo seja sempre tratado como texto."""
    return (
        term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def _normalize(expression):
    """CU03-C1 passo 2: desconsidera acentuação e caixa (extensão unaccent do PostgreSQL).

    O `unaccent` vem antes do `lower` para que a caixa de letras acentuadas não dependa do locale do banco.
    """
    return func.lower(func.unaccent(expression))


class ItemRepository:
    """Acesso a dados da entidade Item (MR: Item.idItem, nome, icone_url) para o CU03.

    Hoje `external_item_id` guarda o idItem do MR (ID do item no WoW). Se `items` for alinhada ao MR,
    só este arquivo precisa mudar.
    """

    def __init__(self, session: Session):
        self.session = session

    def _name_filter(self, term: str):
        pattern = f"%{escape_like(term)}%"
        return _normalize(Item.name).like(_normalize(pattern), escape=LIKE_ESCAPE)

    def search_by_name(self, term: str, offset: int, limit: int) -> tuple[list[Item], int]:
        """CU03-C1 passos 2 e 3: itens cujo nome corresponde (total ou parcialmente) ao termo, e o total geral."""
        name_filter = self._name_filter(term)
        total = self.session.query(func.count(Item.id)).filter(name_filter).scalar() or 0
        items = (
            self.session.query(Item)
            .filter(name_filter)
            .order_by(Item.name, Item.external_item_id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def find_by_external_id(self, external_item_id: str) -> Optional[Item]:
        """CU03-C2 passo 3 / CU03-C3 passo 3: item correspondente ao identificador numérico, se existir."""
        return (
            self.session.query(Item)
            .filter(Item.external_item_id == external_item_id)
            .first()
        )

    def last_auction_update(self, external_item_ids: Iterable[str]) -> dict[str, datetime]:
        """CU03-C1/C2 passo 4: data (UTC) da última atualização do leilão de cada item.

        Fonte provisória: `historical_item_prices` (CU10). Pelo MR a data vem de `Leilao.data_ingestao`,
        tabela que só passa a existir no CU09; trocar a fonte aqui quando ela for criada.
        """
        numeric_ids = {
            int(external_id): external_id
            for external_id in external_item_ids
            if external_id.isascii() and external_id.isdigit()
        }
        if not numeric_ids:
            return {}
        rows = (
            self.session.query(HistoricalItemPrice.item_id, func.max(HistoricalItemPrice.timestamp))
            .filter(HistoricalItemPrice.item_id.in_(numeric_ids.keys()))
            .group_by(HistoricalItemPrice.item_id)
            .all()
        )
        # A coluna guarda UTC sem fuso; devolve com fuso explícito para o cliente não reinterpretar.
        return {numeric_ids[item_id]: last.replace(tzinfo=timezone.utc) for item_id, last in rows}
