import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, ContextManager, Iterator, Optional

from fastapi import Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.repositories.database import get_session
from src.services import security
from src.services.email_service import EmailService
from src.services.erros import ErroDeNegocio

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
