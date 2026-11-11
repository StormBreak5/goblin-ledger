"""CU08 – Manter Notificações (MR, seção 7.2 do TC).

- `notificacao`: o disparo de um alerta de preço (item, tipo, preço-alvo, valor de mercado que o atingiu, canal, data e
  hora), a leitura pela tela (`lida_em`) e o envio por e-mail (`envio_email`, `tentativas_email`, `enviada_em`). Removida
  com a conta (RN20); mantida, com `id_alerta` nulo, quando o alerta é excluído (CU07-C3) ou o favorito removido (CU06-C2).
- `alerta_preco`: índice (situação, item) para o C1 recuperar os alertas ativos dos itens do ciclo.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificacao",
        sa.Column("id_notificacao", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_alerta", sa.Integer(), nullable=True),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("preco_alvo", sa.BigInteger(), nullable=False),
        sa.Column("valor_mercado", sa.BigInteger(), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("disparada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("envio_email", sa.String(length=8), nullable=True),
        sa.Column("tentativas_email", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('COMPRA', 'VENDA')", name="ck_notificacao_tipo"),
        sa.CheckConstraint("canal IN ('WEB', 'EMAIL', 'AMBOS')", name="ck_notificacao_canal"),
        sa.CheckConstraint("envio_email IN ('PENDENTE', 'ENVIADO', 'FALHOU')", name="ck_notificacao_envio_email"),
        sa.CheckConstraint("(canal = 'WEB') = (envio_email IS NULL)", name="ck_notificacao_envio_do_canal"),
        sa.ForeignKeyConstraint(["id_alerta"], ["alerta_preco.id_alerta"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_notificacao"),
    )
    op.create_index("ix_notificacao_usuario_disparada", "notificacao", ["id_usuario", "disparada_em"])
    op.create_index("ix_notificacao_envio_pendente", "notificacao", ["id_notificacao"],
                    postgresql_where=sa.text("envio_email = 'PENDENTE'"))
    op.create_index("ix_alerta_preco_situacao_item", "alerta_preco", ["situacao", "item_id"])


def downgrade() -> None:
    op.drop_index("ix_alerta_preco_situacao_item", table_name="alerta_preco")
    op.drop_index("ix_notificacao_envio_pendente", table_name="notificacao")
    op.drop_index("ix_notificacao_usuario_disparada", table_name="notificacao")
    op.drop_table("notificacao")
