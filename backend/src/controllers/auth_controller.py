from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Response

from src.controllers.deps import (
    extrair_token,
    get_abridor_de_sessao,
    get_email_service,
    get_relogio,
    traduzir_erros,
)
from src.models.auth_models import (
    LoginRequest,
    LoginResponse,
    MensagemResponse,
    PerfilResponse,
    RecuperacaoRequest,
    RedefinicaoRequest,
    TokenRequest,
)
from src.services import mensagens
from src.services.email_service import EmailService
from src.services.login_service import LoginService, ServicoDeEmailIndisponivelError, url_do_frontend

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(
    dados: LoginRequest,
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU02-C1 (RN21): autentica com e-mail e senha e devolve o JWT da sessão (24 h)."""
    with traduzir_erros(mensagens.FALHA_NO_LOGIN), abrir_sessao() as db:
        sessao = LoginService(db, relogio).autenticar(dados.email, dados.senha)
        return LoginResponse(
            access_token=sessao.token,
            expires_at=sessao.expira_em,
            usuario=PerfilResponse(email=sessao.usuario.email, regiao=sessao.usuario.regiao, role=sessao.usuario.role),
        )


@router.post("/auth/logout", status_code=204)
def logout(
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU02-C4: invalida a sessão do token. O navegador remove os dados de sessão por conta própria."""
    with traduzir_erros(mensagens.FALHA_NO_LOGIN), abrir_sessao() as db:
        LoginService(db, relogio).encerrar_sessao(token)
    return Response(status_code=204)


@router.post("/auth/password-recovery", response_model=MensagemResponse)
def solicitar_recuperacao(
    dados: RecuperacaoRequest,
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
    email_service: EmailService = Depends(get_email_service),
):
    """CU02-C2 (RN22): envia o link de redefinição. A resposta é a mesma para e-mail cadastrado e não cadastrado."""
    with traduzir_erros(mensagens.FALHA_NA_RECUPERACAO), abrir_sessao() as db:
        try:
            LoginService(db, relogio, email_service).solicitar_recuperacao(dados.email, url_do_frontend())
        except ServicoDeEmailIndisponivelError as e:
            raise HTTPException(status_code=503, detail=mensagens.FALHA_NA_RECUPERACAO) from e
    return MensagemResponse(message=mensagens.RECUPERACAO_SOLICITADA)


@router.post("/auth/password-reset/validate", status_code=204)
def validar_link_de_redefinicao(
    dados: TokenRequest,
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU02-C3 passo 2 (RN22): o link é válido, está no prazo e ainda não foi usado?
    O token vai no corpo, e não na URL, para não aparecer no log de acesso."""
    with traduzir_erros(mensagens.FALHA_NA_REDEFINICAO), abrir_sessao() as db:
        LoginService(db, relogio).validar_token_de_recuperacao(dados.token)
    return Response(status_code=204)


@router.post("/auth/password-reset", response_model=MensagemResponse)
def redefinir_senha(
    dados: RedefinicaoRequest,
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU02-C3 (RN22): cadastra a nova senha e invalida o token."""
    with traduzir_erros(mensagens.FALHA_NA_REDEFINICAO), abrir_sessao() as db:
        LoginService(db, relogio).redefinir_senha(dados.token, dados.nova_senha, dados.confirmacao_nova_senha)
    return MensagemResponse(message=mensagens.SENHA_REDEFINIDA)
