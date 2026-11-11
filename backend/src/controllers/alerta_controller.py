from typing import Callable, Optional

from fastapi import APIRouter, Depends

from src.controllers.deps import extrair_token, get_abridor_de_sessao, get_relogio, traduzir_erros
from src.models.api_models import AlertaRequest, AlertaSalvoResponse, AlertasDoItemResponse, FormularioDoAlertaResponse
from src.models.auth_models import MensagemResponse
from src.services import mensagens
from src.services.alerta_service import AlertaService
from src.services.login_service import LoginService

router = APIRouter(tags=["alerts"])


@router.get("/items/{item_id}/alerts", response_model=AlertasDoItemResponse)
def listar_alertas(
    item_id: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07: a seção "Alertas de preço" da tela do item, com os alertas do usuário e a cota da RN08."""
    with traduzir_erros(mensagens.FALHA_AO_CARREGAR_ALERTAS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return AlertaService(db, relogio).do_item(usuario.id_usuario, item_id)


@router.get("/items/{item_id}/alerts/new", response_model=FormularioDoAlertaResponse)
def novo_alerta(
    item_id: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07-C1 passos 2 a 4: 409 com a mensagem do FA1 (item fora dos favoritos) ou do FA2 (RN08); senão, o valor de
    mercado atual do item (RN06) como referência do formulário."""
    with traduzir_erros(mensagens.FALHA_AO_CARREGAR_ALERTAS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return AlertaService(db, relogio).novo(usuario.id_usuario, item_id)


@router.post("/items/{item_id}/alerts", response_model=AlertaSalvoResponse, status_code=201)
def criar_alerta(
    item_id: int,
    dados: AlertaRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07-C1 passos 6 a 8 (RN01, RN08). FA3: 422 com a mensagem do cenário. FE1: 503 com a mensagem do cenário."""
    with traduzir_erros(mensagens.FALHA_AO_SALVAR_ALERTA), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return AlertaService(db, relogio).criar(usuario.id_usuario, item_id, dados)


@router.get("/alerts/{id_alerta}/edit", response_model=FormularioDoAlertaResponse)
def alerta_para_editar(
    id_alerta: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07-C2 passos 1 e 2: os dados atuais e o valor de mercado atual. FA2: o alerta disparado só abre para reativar se
    o usuário estiver abaixo da cota (409). Alerta de outro usuário: 404."""
    with traduzir_erros(mensagens.FALHA_AO_CARREGAR_ALERTAS), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return AlertaService(db, relogio).para_editar(usuario.id_usuario, id_alerta)


@router.put("/alerts/{id_alerta}", response_model=AlertaSalvoResponse)
def alterar_alerta(
    id_alerta: int,
    dados: AlertaRequest,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07-C2 passos 4 a 6: altera e, se disparado, reativa (FA1, RN08). FA3: 422. FE1: 503, e o alerta fica como
    estava."""
    with traduzir_erros(mensagens.FALHA_AO_SALVAR_ALERTA), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return AlertaService(db, relogio).alterar(usuario.id_usuario, id_alerta, dados)


@router.delete("/alerts/{id_alerta}", response_model=MensagemResponse)
def excluir_alerta(
    id_alerta: int,
    token: Optional[str] = Depends(extrair_token),
    abrir_sessao: Callable = Depends(get_abridor_de_sessao),
    relogio: Callable = Depends(get_relogio),
):
    """CU07-C3 passos 4 e 5 (a confirmação "Deseja excluir este alerta?" é da tela). FE1: 503, e o alerta é mantido."""
    with traduzir_erros(mensagens.FALHA_AO_EXCLUIR_ALERTA), abrir_sessao() as db:
        usuario = LoginService(db, relogio).usuario_da_sessao(token)
        return MensagemResponse(message=AlertaService(db, relogio).excluir(usuario.id_usuario, id_alerta))
