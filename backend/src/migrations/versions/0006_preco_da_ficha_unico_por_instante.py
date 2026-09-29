"""Ficha do WoW: um preço por instante.

`item_prices` guarda o preço da Ficha (API da Blizzard) e passa a receber também o histórico da Undermine Exchange. O
instante de cada ponto é o do preço na Blizzard (atualizado a cada 20 min), e não o da coleta, então (item, região,
instante) é único. Se já houvesse leituras repetidas para o mesmo instante, fica a primeira.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM item_prices a USING item_prices b "
        "WHERE a.item_id = b.item_id AND a.region = b.region AND a.created_at = b.created_at AND a.id > b.id"
    )
    op.create_unique_constraint("uq_item_prices_item_region_created", "item_prices", ["item_id", "region", "created_at"])


def downgrade() -> None:
    op.drop_constraint("uq_item_prices_item_region_created", "item_prices", type_="unique")
