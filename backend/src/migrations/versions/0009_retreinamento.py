"""CU11-C2 (RF08, RN26): retreinamento semanal do modelo.

- `modelo_preditivo.descartado`: o modelo novo que não superou o vigente (C2-FA2) fica registrado com as métricas.
- `execucao_treinamento`: a versão vigente anterior, a decisão (`SUBSTITUIDO` ou `MANTIDO`), a mediana do MdAPE por
  item de cada modelo no mesmo período de teste e quantos itens foram comparados (passos 6 e 7), e os itens que
  deixaram de ser elegíveis (C2-FA1), com quantos deles estavam liberados.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("modelo_preditivo",
                  sa.Column("descartado", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("execucao_treinamento", sa.Column("versao_anterior", sa.Integer(), nullable=True))
    op.create_foreign_key("execucao_treinamento_versao_anterior_fkey", "execucao_treinamento", "modelo_preditivo",
                          ["versao_anterior"], ["versao"])
    op.add_column("execucao_treinamento", sa.Column("decisao", sa.String(length=12), nullable=True))
    op.create_check_constraint("ck_execucao_treinamento_decisao", "execucao_treinamento",
                               "decisao IN ('SUBSTITUIDO', 'MANTIDO')")
    op.add_column("execucao_treinamento", sa.Column("mdape_novo", sa.Float(), nullable=True))
    op.add_column("execucao_treinamento", sa.Column("mdape_vigente", sa.Float(), nullable=True))
    op.add_column("execucao_treinamento", sa.Column("itens_comparados", sa.Integer(), nullable=True))
    op.add_column("execucao_treinamento", sa.Column("deixaram_de_ser_elegiveis", sa.Integer(), nullable=True))
    op.add_column("execucao_treinamento",
                  sa.Column("liberados_que_deixaram_de_ser_elegiveis", sa.Integer(), nullable=True))


def downgrade() -> None:
    for coluna in ("liberados_que_deixaram_de_ser_elegiveis", "deixaram_de_ser_elegiveis", "itens_comparados",
                   "mdape_vigente", "mdape_novo"):
        op.drop_column("execucao_treinamento", coluna)
    op.drop_constraint("ck_execucao_treinamento_decisao", "execucao_treinamento", type_="check")
    op.drop_column("execucao_treinamento", "decisao")
    op.drop_constraint("execucao_treinamento_versao_anterior_fkey", "execucao_treinamento", type_="foreignkey")
    op.drop_column("execucao_treinamento", "versao_anterior")
    op.drop_column("modelo_preditivo", "descartado")
