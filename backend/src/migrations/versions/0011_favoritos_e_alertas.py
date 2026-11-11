"""CU06 – Manter Favoritos e CU07 – Manter Alerta (MR, seção 7.2 do TC).

- `favorito`: o item na lista do usuário (chave usuário e item), removido com a conta (CU01-C3, RN20).
- `alerta_preco`: o alerta de preço de um item favorito (tipo, preço-alvo em Cobre, canal e situação), removido com a
  conta (RN20) e com o favorito (CU06-C2-FA1), pela chave composta usuário e item.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorito",
        sa.Column("id_usuario", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("item_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("data_inclusao", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_usuario", "item_id"),
    )
    op.create_table(
        "alerta_preco",
        sa.Column("id_alerta", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("preco_alvo", sa.BigInteger(), nullable=False),
        sa.Column("canal", sa.String(length=5), nullable=False),
        sa.Column("situacao", sa.String(length=9), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disparado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('COMPRA', 'VENDA')", name="ck_alerta_preco_tipo"),
        sa.CheckConstraint("canal IN ('WEB', 'EMAIL', 'AMBOS')", name="ck_alerta_preco_canal"),
        sa.CheckConstraint("situacao IN ('ATIVO', 'DISPARADO')", name="ck_alerta_preco_situacao"),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_usuario", "item_id"], ["favorito.id_usuario", "favorito.item_id"],
                                ondelete="CASCADE", name="fk_alerta_preco_favorito"),
        sa.PrimaryKeyConstraint("id_alerta"),
    )
    op.create_index("ix_alerta_preco_usuario_situacao", "alerta_preco", ["id_usuario", "situacao"])
    op.create_index("ix_alerta_preco_usuario_item", "alerta_preco", ["id_usuario", "item_id"])


def downgrade() -> None:
    op.drop_index("ix_alerta_preco_usuario_item", table_name="alerta_preco")
    op.drop_index("ix_alerta_preco_usuario_situacao", table_name="alerta_preco")
    op.drop_table("alerta_preco")
    op.drop_table("favorito")
