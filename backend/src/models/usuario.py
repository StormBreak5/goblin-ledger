import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from src.repositories.database import Base

REGIOES_VALIDAS = ("US", "EU")  # RN11: somente servidores ocidentais
PAPEL_USUARIO = "usuario"
PAPEL_ADMIN = "admin"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    """CU01 / RF01: conta de usuário (MR: Usuario). O e-mail é único e imutável (RN18)."""
    __tablename__ = "usuario"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(150), nullable=False, unique=True)
    senha_hash = Column(String(100), nullable=False)
    regiao = Column(String(2), nullable=False)
    role = Column(String(15), nullable=False, default=PAPEL_USUARIO, server_default=PAPEL_USUARIO)
    data_criacao = Column(DateTime(timezone=True), nullable=False, default=_agora)

    __table_args__ = (
        CheckConstraint("regiao IN ('US', 'EU')", name="ck_usuario_regiao"),
        CheckConstraint("role IN ('usuario', 'admin')", name="ck_usuario_role"),
    )


class Sessao(Base):
    """CU02-C1 / C4: sessão autenticada. `id_sessao` é o `jti` do JWT; a exclusão do usuário a remove (RN20)."""
    __tablename__ = "sessao"

    id_sessao = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    emitida_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    revogada_em = Column(DateTime(timezone=True), nullable=True)


class TokenRecuperacao(Base):
    """CU02-C2 / C3 (RN22): token de recuperação de senha. Só o hash do token é armazenado."""
    __tablename__ = "token_recuperacao"

    id_token = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    invalidado_em = Column(DateTime(timezone=True), nullable=True)  # usado ou substituído por um link mais novo


class TentativaLogin(Base):
    """CU02-C1 (RN21): tentativas consecutivas malsucedidas por e-mail. Sem chave estrangeira, para valer
    também para e-mails sem conta (o bloqueio não revela se o e-mail existe)."""
    __tablename__ = "tentativa_login"

    email = Column(String(150), primary_key=True)
    falhas = Column(Integer, nullable=False, default=0)
    bloqueado_ate = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=_agora)
