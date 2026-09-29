"""Baseline: esquema existente antes do Alembic (itens, preços e coleta) e extensão unaccent.

Idempotente: cada tabela só é criada se ainda não existir, então a migração roda igual em um banco novo e em
um banco criado antes pelo `create_all` (que não precisa de `alembic stamp`).

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CU03-C1 passo 2: busca de itens sem considerar acentuação.
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("items"):
        op.create_table(
            "items",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("game", sa.String(length=50), nullable=False),
            sa.Column("external_item_id", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("icon_url", sa.String(length=255), nullable=True),
            sa.Column("metadata_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_items_game", "items", ["game"])
        op.create_index("ix_items_external_item_id", "items", ["external_item_id"])
        op.create_index("idx_items_game_external_id", "items", ["game", "external_item_id"], unique=True)

    if not inspector.has_table("item_prices"):
        op.create_table(
            "item_prices",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("price_copper", sa.BigInteger(), nullable=False),
            sa.Column("region", sa.String(length=5), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_item_region_created_at", "item_prices", ["item_id", "region", "created_at"])

    if not inspector.has_table("historical_item_prices"):
        op.create_table(
            "historical_item_prices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("region", sa.String(length=50), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("price", sa.BigInteger(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("item_id", "region", "timestamp", name="uq_item_region_timestamp"),
        )
        op.create_index("ix_historical_item_prices_item_id", "historical_item_prices", ["item_id"])
        op.create_index("ix_historical_item_prices_region", "historical_item_prices", ["region"])
        op.create_index("ix_historical_item_prices_timestamp", "historical_item_prices", ["timestamp"])

    if not inspector.has_table("scraper_execution_logs"):
        op.create_table(
            "scraper_execution_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("execution_start", sa.DateTime(), nullable=False),
            sa.Column("execution_end", sa.DateTime(), nullable=True),
            sa.Column("status", sa.Enum("RUNNING", "SUCCESS", "FAILED", name="executionstatus"), nullable=False),
            sa.Column("items_processed", sa.Integer(), nullable=True),
            sa.Column("records_inserted", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    raise NotImplementedError("A migração baseline não é reversível: ela descreve o esquema que já existia.")
