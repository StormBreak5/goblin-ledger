"""CU09 (RF07 / RF10): ingestão de dados de mercado da Blizzard.

Tabelas `reino`, `leilao` (MR: Reino e Leilao, com preços em BIGINT pela RN01, a chave do leilão na Blizzard e a
situação da RN04), `ciclo_ingestao` (última requisição por endpoint, RN05, e resumo do ciclo) e `estado_mercado`
(frescor e "Dados Desatualizados", RN09/RN14). A tabela `historical_item_prices` ganha `origem` e `anomalia`:
adicionar colunas com valor padrão é só metadado no PostgreSQL 11+, então não reescreve as linhas existentes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "historical_item_prices",
        sa.Column("origem", sa.String(length=10), server_default="UNDERMINE", nullable=False),
    )
    op.add_column(
        "historical_item_prices",
        sa.Column("anomalia", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "reino",
        sa.Column("id_reino", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("nome", sa.String(length=45), nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.CheckConstraint("regiao IN ('US', 'EU')", name="ck_reino_regiao"),
        sa.PrimaryKeyConstraint("id_reino"),
    )

    op.create_table(
        "leilao",
        sa.Column("id_leilao", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("id_leilao_origem", sa.BigInteger(), nullable=False),
        sa.Column("id_reino", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("preco_bid", sa.BigInteger(), nullable=True),
        sa.Column("preco_buyout", sa.BigInteger(), nullable=True),
        sa.Column("preco_unitario", sa.BigInteger(), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("tempo_restante", sa.String(length=10), nullable=True),
        sa.Column("situacao", sa.String(length=20), server_default="ATIVO", nullable=False),
        sa.Column("data_ingestao", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("situacao IN ('ATIVO', 'EXPIRADO_VENDIDO')", name="ck_leilao_situacao"),
        sa.ForeignKeyConstraint(["id_reino"], ["reino.id_reino"]),
        sa.PrimaryKeyConstraint("id_leilao"),
        sa.UniqueConstraint("id_reino", "id_leilao_origem", name="uq_leilao_reino_origem"),
    )
    op.create_index("ix_leilao_item_reino_ingestao", "leilao", ["item_id", "id_reino", "data_ingestao"])
    op.create_index("ix_leilao_data_ingestao", "leilao", ["data_ingestao"])

    op.create_table(
        "ciclo_ingestao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.String(length=60), nullable=False),
        sa.Column("origem", sa.String(length=10), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("data_referencia", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leiloes_coletados", sa.Integer(), nullable=False),
        sa.Column("leiloes_descartados", sa.Integer(), nullable=False),
        sa.Column("itens_atualizados", sa.Integer(), nullable=False),
        sa.Column("itens_anomalos", sa.Integer(), nullable=False),
        sa.Column("etapa_da_falha", sa.String(length=20), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ciclo_ingestao_endpoint_inicio", "ciclo_ingestao", ["endpoint", "iniciado_em"])

    op.create_table(
        "estado_mercado",
        sa.Column("mercado", sa.String(length=60), nullable=False),
        sa.Column("id_reino", sa.Integer(), nullable=False),
        sa.Column("ultima_atualizacao_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desatualizado", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ultima_falha_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_reino"], ["reino.id_reino"]),
        sa.PrimaryKeyConstraint("mercado"),
        sa.UniqueConstraint("id_reino"),
    )


def downgrade() -> None:
    op.drop_table("estado_mercado")
    op.drop_index("ix_ciclo_ingestao_endpoint_inicio", table_name="ciclo_ingestao")
    op.drop_table("ciclo_ingestao")
    op.drop_index("ix_leilao_data_ingestao", table_name="leilao")
    op.drop_index("ix_leilao_item_reino_ingestao", table_name="leilao")
    op.drop_table("leilao")
    op.drop_table("reino")
    op.drop_column("historical_item_prices", "anomalia")
    op.drop_column("historical_item_prices", "origem")
