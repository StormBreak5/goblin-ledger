from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query

from src.controllers.deps import extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.api_models import FavoritoResponse, FavoritosResponse
from src.services import mensagens
from src.services.favorito_service import FavoritoService
from src.services.login_service import LoginService

router = APIRouter(tags=["favorites"])


@router.post("/favorites/{item_id}", response_model=FavoritoResponse)
def adicionar_favorito(
    item_id: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU06-C1 (RF09): adiciona o item aos favoritos. FA1: sem sessão válida, 401 (a tela leva ao login). FA2: o item já
    favoritado não é erro. FE1: falha de banco, 503 com a mensagem do cenário."""
    with traduzir_erros(mensagens.FALHA_NOS_FAVORITOS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return FavoritoService(db, relogio).adicionar(usuario.id_usuario, item_id)


@router.delete("/favorites/{item_id}", response_model=FavoritoResponse)
def remover_favorito(
    item_id: int,
    confirmar: bool = Query(False, description="CU06-C2-FA1: o usuário confirmou a exclusão dos alertas do item."),
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU06-C2: remove o item dos favoritos. FA1: com alertas do item e sem `confirmar`, 409 com o aviso do cenário e nada
    é removido. FE1: falha de banco, 503, e as remoções são desfeitas."""
    with traduzir_erros(mensagens.FALHA_NOS_FAVORITOS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return FavoritoService(db, relogio).remover(usuario.id_usuario, item_id, confirmar)


@router.get("/favorites", response_model=FavoritosResponse)
def listar_favoritos(
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU06-C3: a lista de favoritos, com o valor de mercado, a variação em relação ao dia anterior, os alertas ativos e
    o selo "Dados Desatualizados" (FA2). FA1: lista vazia. FE1: falha de banco, 503 com a mensagem do cenário."""
    with traduzir_erros(mensagens.FALHA_NA_LISTA_DE_FAVORITOS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return FavoritoService(db, relogio).listar(usuario.id_usuario)
