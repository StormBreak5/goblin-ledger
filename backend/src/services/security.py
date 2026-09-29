import base64
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
DURACAO_DA_SESSAO = timedelta(hours=24)  # decisão do autor: JWT com tempo limite de 24 h (não renovável)

_segredo_efemero: Optional[str] = None


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _prehash(senha: str) -> bytes:
    """O bcrypt só considera os 72 primeiros bytes (e a v5 rejeita mais que isso), mas o RF01 aceita senhas de até
    255 caracteres: o SHA-256 em base64 (44 bytes) entra no lugar da senha, sem truncar."""
    return base64.b64encode(hashlib.sha256(senha.encode("utf-8")).digest())


def gerar_hash_da_senha(senha: str) -> str:
    """CU01-C1 passo 6 / CU01-C2 passo 7 / CU02-C3 passo 6 (RNF06): hash bcrypt. Só o hash é armazenado."""
    rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(_prehash(senha), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def senha_confere(senha: str, senha_hash: str) -> bool:
    """CU01-C2 passo 6 / CU01-C3 passo 4 / CU02-C1 passo 6: confere a senha informada com o hash armazenado."""
    try:
        return bcrypt.checkpw(_prehash(senha), senha_hash.encode("ascii"))
    except ValueError:
        return False


def gastar_tempo_de_verificacao(senha: str) -> None:
    """CU02-C1-FA2: para e-mail sem conta, gasta o mesmo tempo de uma conferência real, para o tempo de resposta
    não revelar se a conta existe."""
    gerar_hash_da_senha(senha)


def _segredo_do_jwt() -> str:
    """JWT_SECRET vem do ambiente. Sem ele, usa um segredo efêmero (os tokens deixam de valer ao reiniciar);
    nunca há segredo fixo no código."""
    global _segredo_efemero
    segredo = os.getenv("JWT_SECRET")
    if segredo:
        return segredo
    if _segredo_efemero is None:
        _segredo_efemero = secrets.token_urlsafe(48)
        logger.warning("JWT_SECRET não definido: usando um segredo efêmero. As sessões serão perdidas ao reiniciar a API.")
    return _segredo_efemero


def emitir_token(id_usuario: int, id_sessao: uuid.UUID, emitido_em: datetime, expira_em: datetime) -> str:
    """CU02-C1 passo 7: JWT da sessão. O `jti` liga o token à linha de `sessao`, que permite encerrá-la (C4)."""
    payload = {
        "sub": str(id_usuario),
        "jti": str(id_sessao),
        "iat": int(emitido_em.timestamp()),
        "exp": int(expira_em.timestamp()),
    }
    return jwt.encode(payload, _segredo_do_jwt(), algorithm=JWT_ALGORITHM)


def ler_token(token: str) -> Optional[dict]:
    """Confere a assinatura e devolve o conteúdo; None se o token for inválido. A expiração é conferida pela
    sessão (relógio injetável), não aqui."""
    try:
        return jwt.decode(token, _segredo_do_jwt(), algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
    except jwt.PyJWTError:
        return None


def gerar_token_de_recuperacao() -> str:
    """CU02-C2 passo 6 (RN22): token de uso único, imprevisível."""
    return secrets.token_urlsafe(32)


def hash_do_token(token: str) -> str:
    """RN22: só o hash do token de recuperação é armazenado."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
