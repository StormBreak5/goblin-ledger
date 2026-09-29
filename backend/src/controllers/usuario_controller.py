from fastapi import APIRouter, Depends, Response
from typing import Callable, Optional

from src.controllers.deps import extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.auth_models import (
    AlteracaoRequest,
    CadastroRequest,
    ExclusaoRequest,
    MensagemResponse,
    PerfilResponse,
)
from src.services import mensagens
from src.services.login_service import LoginService
from src.services.usuario_service import UsuarioService

router = APIRouter(tags=["users"])


@router.post("/users", response_model=MensagemResponse, status_code=201)
def cadastrar_usuario(
    dados: CadastroRequest,
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU01-C1 (RF01): cadastra a conta com e-mail, senha, confirmação e região (US/EU)."""
    with traduzir_erros(mensagens.FALHA_NO_CADASTRO), abrir_sessao() as db:
        UsuarioService(db, relogio).cadastrar(dados.email, dados.senha, dados.confirmacao_senha, dados.regiao)
    return MensagemResponse(message=mensagens.CONTA_CRIADA)


@router.get("/users/me", response_model=PerfilResponse)
def ver_perfil(
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU01-C2 passo 2: dados do usuário autenticado (e-mail somente leitura, RN18).
    O documento não define mensagem para falha ao carregar o perfil; usa a do CU01-C2-FE1."""
    with traduzir_erros(mensagens.FALHA_NA_ATUALIZACAO), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return PerfilResponse(email=usuario.email, regiao=usuario.regiao, role=usuario.role)


@router.put("/users/me", response_model=MensagemResponse)
def alterar_dados(
    dados: AlteracaoRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU01-C2 (RN18/RN19): altera a região e, se informada, a senha."""
    with traduzir_erros(mensagens.FALHA_NA_ATUALIZACAO), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        UsuarioService(db, relogio).alterar_dados(
            usuario, dados.regiao, dados.senha_atual, dados.nova_senha, dados.confirmacao_nova_senha
        )
    return MensagemResponse(message=mensagens.DADOS_ATUALIZADOS)


@router.delete("/users/me", status_code=204)
def excluir_conta(
    dados: ExclusaoRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU01-C3 (RN19/RN20): exclui definitivamente a conta e os dados vinculados, mediante a senha."""
    with traduzir_erros(mensagens.FALHA_NA_EXCLUSAO), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        UsuarioService(db, relogio).excluir_conta(usuario, dados.senha)
    return Response(status_code=204)
