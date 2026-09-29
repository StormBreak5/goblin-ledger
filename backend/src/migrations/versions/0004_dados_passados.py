"""CU10 (RF11): dados passados.

`historical_item_prices.granularidade` (RN16) identifica se o ponto é diário ou horário; as linhas existentes ficam
`DIARIA`, exceto as do ciclo da Blizzard (CU09), que são horárias. Adicionar a coluna com valor padrão constante é só
metadado no PostgreSQL 11+, então as milhões de linhas existentes não são reescritas; o UPDATE toca apenas as poucas
linhas da Blizzard.

`scraper_execution_logs` ganha o pedido e o resumo da importação (CU10-C1). As tabelas `evento_jogo` e
`extracao_evento` (CU10-C2, RN17) e `aptidao_treinamento` (CU10-C3, RN15) são novas.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS = "'EXPANSAO', 'PATCH', 'TEMPORADA', 'EVENTO_SAZONAL', 'RECORRENTE', 'OUTRO'"
REGIOES = "'US', 'EU', 'GLOBAL'"
ORIGENS = "'WIKIPEDIA', 'WARCRAFT_WIKI', 'API_BLIZZARD', 'REGRA', 'MANUAL'"


def upgrade() -> None:
    op.add_column(
        "historical_item_prices",
        sa.Column("granularidade", sa.String(length=10), server_default="DIARIA", nullable=False),
    )
    op.execute("UPDATE historical_item_prices SET granularidade = 'HORARIA' WHERE origem = 'BLIZZARD'")

    op.add_column("scraper_execution_logs", sa.Column("triggered_by", sa.String(length=15), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("region", sa.String(length=50), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("items_requested", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("items_created", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("items_without_data", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("items_failed", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("records_discarded", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("records_duplicated", sa.Integer(), nullable=True))
    op.add_column("scraper_execution_logs", sa.Column("failure_stage", sa.String(length=10), nullable=True))

    op.create_table(
        "evento_jogo",
        sa.Column("id_evento", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("versao", sa.String(length=20), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=True),
        sa.Column("regiao", sa.String(length=6), server_default="GLOBAL", nullable=False),
        sa.Column("origem", sa.String(length=15), nullable=False),
        sa.Column("fonte", sa.String(length=255), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"tipo IN ({TIPOS})", name="ck_evento_jogo_tipo"),
        sa.CheckConstraint(f"regiao IN ({REGIOES})", name="ck_evento_jogo_regiao"),
        sa.CheckConstraint(f"origem IN ({ORIGENS})", name="ck_evento_jogo_origem"),
        sa.CheckConstraint("data_fim IS NULL OR data_fim >= data_inicio", name="ck_evento_jogo_periodo"),
        sa.PrimaryKeyConstraint("id_evento"),
        sa.UniqueConstraint("tipo", "nome", "data_inicio", "regiao", name="uq_evento_jogo"),
    )
    op.create_index("ix_evento_jogo_data_inicio", "evento_jogo", ["data_inicio"])

    op.create_table(
        "extracao_evento",
        sa.Column("id_extracao", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fonte", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("eventos_encontrados", sa.Integer(), nullable=False),
        sa.Column("eventos_registrados", sa.Integer(), nullable=False),
        sa.Column("eventos_ignorados", sa.Integer(), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id_extracao"),
    )
    op.create_index("ix_extracao_evento_fonte_inicio", "extracao_evento", ["fonte", "iniciada_em"])

    op.create_table(
        "aptidao_treinamento",
        sa.Column("item_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("apto", sa.Boolean(), nullable=False),
        sa.Column("periodo_continuo_dias", sa.Integer(), nullable=False),
        sa.Column("inicio_periodo", sa.Date(), nullable=True),
        sa.Column("fim_periodo", sa.Date(), nullable=True),
        sa.Column("dias_com_dados", sa.Integer(), nullable=False),
        sa.Column("validado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
    )


def downgrade() -> None:
    op.drop_table("aptidao_treinamento")
    op.drop_index("ix_extracao_evento_fonte_inicio", table_name="extracao_evento")
    op.drop_table("extracao_evento")
    op.drop_index("ix_evento_jogo_data_inicio", table_name="evento_jogo")
    op.drop_table("evento_jogo")
    for coluna in (
        "failure_stage", "records_duplicated", "records_discarded", "items_failed", "items_without_data", "items_created",
        "items_requested", "region", "triggered_by",
    ):
        op.drop_column("scraper_execution_logs", coluna)
    op.drop_column("historical_item_prices", "granularidade")
