import os
import re
from typing import Optional

from src.models.usuario import REGIOES_VALIDAS

EMAIL_MAX = 150  # RF01 – E-mail: texto de até 150 caracteres
SENHA_MAX = 255  # RF01 – Senha: texto de até 255 caracteres
# O documento não define regra de complexidade: o mínimo é configurável (ver PASSWORD_MIN_LENGTH no .env.example).
SENHA_MIN = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))

_FORMATO_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalizar_email(email: str) -> str:
    """O e-mail identifica a conta (RN18): comparado e gravado sem espaços nas pontas e em minúsculas."""
    return (email or "").strip().lower()


def email_valido(email: str) -> bool:
    """RF01: formato de e-mail válido, de até 150 caracteres."""
    return bool(email) and len(email) <= EMAIL_MAX and _FORMATO_EMAIL.fullmatch(email) is not None


def senha_valida(senha: str) -> bool:
    return SENHA_MIN <= len(senha or "") <= SENHA_MAX


def normalizar_regiao(regiao: str) -> Optional[str]:
    """RN11: somente US ou EU. Devolve None se a região for inválida."""
    valor = (regiao or "").strip().upper()
    return valor if valor in REGIOES_VALIDAS else None
