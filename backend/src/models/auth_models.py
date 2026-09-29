from datetime import datetime

from pydantic import BaseModel

# Todos os campos das requisições têm padrão vazio: a validação e as mensagens são do serviço (CU01-C1-FA1 etc.),
# e não do 422 genérico do FastAPI.


class CadastroRequest(BaseModel):
    email: str = ""
    senha: str = ""
    confirmacao_senha: str = ""
    regiao: str = ""


class AlteracaoRequest(BaseModel):
    regiao: str = ""
    senha_atual: str = ""
    nova_senha: str = ""
    confirmacao_nova_senha: str = ""


class ExclusaoRequest(BaseModel):
    senha: str = ""


class LoginRequest(BaseModel):
    email: str = ""
    senha: str = ""


class RecuperacaoRequest(BaseModel):
    email: str = ""


class TokenRequest(BaseModel):
    token: str = ""


class RedefinicaoRequest(BaseModel):
    token: str = ""
    nova_senha: str = ""
    confirmacao_nova_senha: str = ""


class MensagemResponse(BaseModel):
    message: str


class PerfilResponse(BaseModel):
    """CU01-C2 passo 2: dados do usuário; o e-mail é somente leitura (RN18)."""
    email: str
    regiao: str
    role: str


class LoginResponse(BaseModel):
    """CU02-C1 passo 7: sessão autenticada."""
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    usuario: PerfilResponse
