"""CU01 / CU02 (RF01): usuário, sessão, token de recuperação de senha e controle de tentativas de login.

`usuario` segue o MR do TC (Usuario) com os ajustes registrados no plano: `regiao` acrescentada (RF01/CU01),
`nome_usuario` omitido (o formulário do CU01 não o tem) e e-mail com 150 caracteres (RF01). As chaves
estrangeiras para `usuario` usam ON DELETE CASCADE (RN20).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id_usuario", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("senha_hash", sa.String(length=100), nullable=False),
        sa.Column("regiao", sa.String(length=2), nullable=False),
        sa.Column("role", sa.String(length=15), server_default="usuario", nullable=False),
        sa.Column("data_criacao", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("regiao IN ('US', 'EU')", name="ck_usuario_regiao"),
        sa.CheckConstraint("role IN ('usuario', 'admin')", name="ck_usuario_role"),
        sa.PrimaryKeyConstraint("id_usuario"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "sessao",
        sa.Column("id_sessao", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("emitida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_sessao"),
    )
    op.create_index("ix_sessao_id_usuario", "sessao", ["id_usuario"])

    op.create_table(
        "token_recuperacao",
        sa.Column("id_token", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_token"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_token_recuperacao_id_usuario", "token_recuperacao", ["id_usuario"])

    op.create_table(
        "tentativa_login",
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("falhas", sa.Integer(), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("tentativa_login")
    op.drop_index("ix_token_recuperacao_id_usuario", table_name="token_recuperacao")
    op.drop_table("token_recuperacao")
    op.drop_index("ix_sessao_id_usuario", table_name="sessao")
    op.drop_table("sessao")
    op.drop_table("usuario")
