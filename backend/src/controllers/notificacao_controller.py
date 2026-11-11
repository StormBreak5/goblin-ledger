from typing import Callable, Optional

from fastapi import APIRouter, Depends

from src.controllers.deps import extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.api_models import MarcarLidasRequest, NaoLidasResponse, NotificacoesResponse
from src.services import mensagens
from src.services.login_service import LoginService
from src.services.notificacao_service import NotificacaoService

router = APIRouter(tags=["notifications"])


@router.get("/notifications/unread-count", response_model=NaoLidasResponse)
def contar_nao_lidas(
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU08-C3 passo 1: a quantidade de notificações não lidas do usuário, para o ícone de sino (consultada ao carregar a
    página e a cada 5 minutos). Sem sessão válida, 401; falha de banco, 503 (FE1)."""
    with traduzir_erros(mensagens.FALHA_NAS_NOTIFICACOES), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return NotificacaoService(db, relogio).nao_lidas(usuario.id_usuario)


@router.get("/notifications", response_model=NotificacoesResponse)
def listar_notificacoes(
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU08-C3 passos 3 e 4: as notificações do usuário com o canal tela, da mais recente para a mais antiga, destacando as
    não lidas. FA1: lista vazia com a mensagem do cenário. FE1: falha de banco, 503 com a mensagem do cenário. A leitura
    não tem efeito colateral: a marcação como lidas é o `POST /notifications/read` (passo 5)."""
    with traduzir_erros(mensagens.FALHA_NAS_NOTIFICACOES), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return NotificacaoService(db, relogio).listar(usuario.id_usuario)


@router.post("/notifications/read", response_model=NaoLidasResponse)
def marcar_como_lidas(
    dados: MarcarLidasRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU08-C3 passo 5: marca como lidas as notificações exibidas (só as do próprio usuário) e devolve o contador zerado.
    FE1: falha de banco, 503 com a mensagem do cenário."""
    with traduzir_erros(mensagens.FALHA_NAS_NOTIFICACOES), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return NotificacaoService(db, relogio).marcar_como_lidas(usuario.id_usuario, dados)
