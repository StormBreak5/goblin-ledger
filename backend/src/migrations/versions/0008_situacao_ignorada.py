"""CU11-C1 (ajustes): situação "Ignorada", liberados sem amostra de treino e último dia usado.

- RF08: o domínio da situação da projeção passa a ser 'Liberada', 'Bloqueada' ou 'Ignorada' (C1-FA3). Os registros
  `IGNORADO` gravados pelo primeiro treinamento passam a `IGNORADA`.
- `execucao_treinamento.liberados_sem_amostra_de_treino`: liberados sem nenhuma amostra no período de treinamento. Nas
  execuções anteriores, o serviço `modelo` preenche o valor a partir do artefato da versão (avaliacao_teste.parquet).
- `execucao_treinamento.ultimo_dia`: último dia encerrado da série usada (RN25).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_projecao_item_situacao", "projecao_item", type_="check")
    op.execute("UPDATE projecao_item SET situacao = 'IGNORADA' WHERE situacao = 'IGNORADO'")
    op.create_check_constraint("ck_projecao_item_situacao", "projecao_item",
                               "situacao IN ('LIBERADA', 'BLOQUEADA', 'IGNORADA')")
    op.add_column("execucao_treinamento", sa.Column("liberados_sem_amostra_de_treino", sa.Integer(), nullable=True))
    op.add_column("execucao_treinamento", sa.Column("ultimo_dia", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("execucao_treinamento", "ultimo_dia")
    op.drop_column("execucao_treinamento", "liberados_sem_amostra_de_treino")
    op.drop_constraint("ck_projecao_item_situacao", "projecao_item", type_="check")
    op.execute("UPDATE projecao_item SET situacao = 'IGNORADO' WHERE situacao = 'IGNORADA'")
    op.create_check_constraint("ck_projecao_item_situacao", "projecao_item",
                               "situacao IN ('LIBERADA', 'BLOQUEADA', 'IGNORADO')")
