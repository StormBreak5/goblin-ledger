import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, ContextManager, Iterator, Optional

from fastapi import Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.usuario import PAPEL_ADMIN, Usuario
from src.repositories.database import get_session
from src.services import security
from src.services.api_client import BlizzardApiClient
from src.services.email_service import EmailService
from src.services.erros import AcessoNegadoError, ErroDeNegocio
from src.services.login_service import LoginService

logger = logging.getLogger(__name__)


@contextmanager
def sessao_do_banco() -> Iterator[Session]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def get_abridor_de_sessao() -> Callable[[], ContextManager[Session]]:
    """A sessão é aberta dentro de `traduzir_erros`: uma falha ao obtê-la também vira a mensagem do fluxo (FE1)."""
    return sessao_do_banco


def get_relogio() -> Callable[[], datetime]:
    return security.agora


def get_email_service() -> EmailService:
    return EmailService()


def criar_cliente_blizzard() -> BlizzardApiClient:
    """CU09: cliente da API da Blizzard (OAuth client credentials). Sem as credenciais, a ingestão não pode rodar."""
    client_id, client_secret = os.getenv("BLIZZARD_CLIENT_ID"), os.getenv("BLIZZARD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="As credenciais da API da Blizzard não estão configuradas.")
    return BlizzardApiClient(client_id, client_secret)


def get_fabrica_de_cliente_blizzard() -> Callable[[], BlizzardApiClient]:
    """Devolve a fábrica, e não o cliente: a checagem do Admin vem antes de qualquer detalhe de configuração."""
    return criar_cliente_blizzard


def exigir_admin(db: Session, token: Optional[str], relogio: Callable[[], datetime]) -> Usuario:
    """CU09-C4 (pré-condição): o usuário da sessão deve ter o papel de Admin (CU01). Sessão inválida: 401;
    usuário comum: AcessoNegadoError (403)."""
    usuario = LoginService(db, relogio).usuario_da_sessao(token)
    if usuario.role != PAPEL_ADMIN:
        raise AcessoNegadoError()
    return usuario


def extrair_token(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """Token do cabeçalho `Authorization: Bearer <jwt>`; None se ausente ou malformado."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


@contextmanager
def traduzir_erros(mensagem_de_falha_do_banco: str) -> Iterator[None]:
    """Traduz para HTTP os erros dos CU01 e CU02: os fluxos alternativos (ErroDeNegocio) viram o status e o texto do
    cenário, e uma falha de banco vira 503 com a mensagem do fluxo de exceção. O detalhe técnico só vai para o log."""
    try:
        yield
    except ErroDeNegocio as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalhe) from e
    except SQLAlchemyError as e:
        logger.exception("Falha de banco de dados: %s", mensagem_de_falha_do_banco)
        raise HTTPException(status_code=503, detail=mensagem_de_falha_do_banco) from e
