"""CU11-C3 (RN13): consolidação diária das predições.

- `consolidacao_diaria`: um registro por região e dia de referência, com o status (o FE1 reprocessa os dias sem
  `SUCESSO`), o que foi encontrado da importação diária, as predições preenchidas e "N/D", os itens bloqueados por
  degradação (FA3), as previsões gravadas (passo 7) e se o retreinamento foi antecipado (FA4).
- `predicao_diaria.consolidado_em`: quando o dia previsto foi consolidado; com ele, preço real e erro nulos são "N/D".

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("predicao_diaria", sa.Column("consolidado_em", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "consolidacao_diaria",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=True),
        sa.Column("importacao_diaria", sa.String(length=12), nullable=True),
        sa.Column("predicoes_do_dia", sa.Integer(), nullable=True),
        sa.Column("predicoes_preenchidas", sa.Integer(), nullable=True),
        sa.Column("predicoes_nd", sa.Integer(), nullable=True),
        sa.Column("itens_liberados_no_inicio", sa.Integer(), nullable=True),
        sa.Column("itens_bloqueados_degradacao", sa.Integer(), nullable=True),
        sa.Column("previsoes_gravadas", sa.Integer(), nullable=True),
        sa.Column("itens_sem_janela", sa.Integer(), nullable=True),
        sa.Column("retreinamento_antecipado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id_execucao_retreinamento", sa.Integer(), nullable=True),
        sa.Column("avisos", sa.Text(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('SUCESSO', 'FALHA')", name="ck_consolidacao_diaria_status"),
        sa.CheckConstraint("importacao_diaria IN ('CONCLUIDA', 'EM_ANDAMENTO', 'FALHA', 'NAO_RODOU')",
                           name="ck_consolidacao_diaria_importacao"),
        sa.ForeignKeyConstraint(["versao"], ["modelo_preditivo.versao"]),
        sa.ForeignKeyConstraint(["id_execucao_retreinamento"], ["execucao_treinamento.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regiao", "dia", name="uq_consolidacao_diaria"),
    )


def downgrade() -> None:
    op.drop_table("consolidacao_diaria")
    op.drop_column("predicao_diaria", "consolidado_em")
