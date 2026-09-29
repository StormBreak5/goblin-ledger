"""CU10 (RN16): corrige a granularidade dos pontos do ciclo horário da Blizzard (CU09).

A migração 0004 marcou como `HORARIA` os pontos da Blizzard que já existiam, mas o INSERT do ciclo do CU09 não
gravava a coluna nova e os pontos criados depois dela receberam o padrão `DIARIA`. O código passa a gravar
`HORARIA`; esta migração corrige as linhas já gravadas. O UPDATE toca só as linhas da origem BLIZZARD (poucas
dezenas de milhares), e não a tabela inteira.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE historical_item_prices SET granularidade = 'HORARIA' WHERE origem = 'BLIZZARD' AND granularidade <> 'HORARIA'")


def downgrade() -> None:
    # Sem perda: a granularidade dos pontos da Blizzard continua correta (horária); só a 0004 pode removê-la.
    pass
