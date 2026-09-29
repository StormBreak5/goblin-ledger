import logging
from datetime import datetime
from typing import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from src.controllers.deps import get_relogio
from src.models.api_models import HistoricoDoItemResponse, ItemDetail, ItemSearchResponse
from src.repositories.database import get_session
from src.services import mensagens
from src.services.item_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MSG_FALHA_NA_BUSCA,
    SEARCH_MAX_LENGTH,
    InvalidSearchTermError,
    ItemNotFoundError,
    ItemService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["items"])

def get_item_service() -> Iterator[ItemService]:
    """CU03-C1-FE1 / CU03-C2-FE1: falha ao obter a sessão do banco também resulta na mensagem do cenário."""
    try:
        db = get_session()
    except SQLAlchemyError as e:
        logger.exception("CU03: não foi possível obter a sessão do banco de dados")
        raise HTTPException(status_code=503, detail=MSG_FALHA_NA_BUSCA) from e
    try:
        yield ItemService(db)
    finally:
        db.close()

def get_servico_do_historico(relogio: Callable[[], datetime] = Depends(get_relogio)) -> Iterator[ItemService]:
    """CU04-C1-FE1: falha ao obter a sessão do banco também resulta na mensagem do cenário."""
    try:
        db = get_session()
    except SQLAlchemyError as e:
        logger.exception("CU04: não foi possível obter a sessão do banco de dados")
        raise HTTPException(status_code=503, detail=mensagens.FALHA_NO_HISTORICO) from e
    try:
        yield ItemService(db, relogio)
    finally:
        db.close()

@router.get("/items/search", response_model=ItemSearchResponse)
def search_items(
    q: str = Query(..., max_length=SEARCH_MAX_LENGTH, description="Termo de busca: nome do item ou identificador numérico"),
    page: int = Query(1, ge=1, description="Página da relação de resultados"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Quantidade de itens por página"),
    service: ItemService = Depends(get_item_service)
):
    """
    CU03-C1 / CU03-C2 (RF02): busca itens por nome (sem considerar acentuação e caixa)
    ou por identificador numérico, com resultado paginado.
    """
    try:
        return service.search_items(query=q, page=page, page_size=page_size)
    except InvalidSearchTermError as e:
        # CU03-C1-FA1: a consulta não é executada.
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SQLAlchemyError as e:
        # CU03-C1-FE1 / CU03-C2-FE1: o detalhe técnico vai para o log, nunca para o usuário.
        logger.exception("CU03: falha ao consultar itens no banco de dados")
        raise HTTPException(status_code=503, detail=MSG_FALHA_NA_BUSCA) from e

@router.get("/items/{item_id}", response_model=ItemDetail)
def get_item(
    item_id: int,
    service: ItemService = Depends(get_item_service)
):
    """
    CU03-C3: recupera o item selecionado na relação de resultados.
    Item inexistente resulta em 404 com a mensagem do CU03-C3-FE1.
    """
    try:
        return service.get_item(item_id=item_id)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SQLAlchemyError as e:
        logger.exception("CU03: falha ao consultar o item %s no banco de dados", item_id)
        raise HTTPException(status_code=503, detail=MSG_FALHA_NA_BUSCA) from e

@router.get("/items/{item_id}/history", response_model=HistoricoDoItemResponse)
def get_item_history(
    item_id: int,
    window: str = Query("14D", description="Janela de tempo: 14D, 30D, 90D, 365D ou ALL"),
    service: ItemService = Depends(get_servico_do_historico),
):
    """
    CU04-C1 / C2: série de preços e volume do item na janela pedida, com a situação dos dados (avisos com o texto do
    cenário). Falha de banco resulta em 503 com a mensagem do CU04-C1-FE1; o detalhe técnico só vai para o log.
    """
    try:
        return service.get_item_history(item_id=item_id, window=window)
    except SQLAlchemyError as e:
        logger.exception("CU04: falha ao consultar o histórico do item %s no banco de dados", item_id)
        raise HTTPException(status_code=503, detail=mensagens.FALHA_NO_HISTORICO) from e

@router.get("/items/{item_id}/current-auctions")
def get_current_auctions(
    item_id: int,
    service: ItemService = Depends(get_servico_do_historico),
):
    """
    Recupera os leilões atuais do item (último ciclo de ingestão): menor preço, quantidade e valor de mercado (RN06).
    """
    try:
        return service.get_current_auctions(item_id=item_id)
    except SQLAlchemyError as e:
        logger.exception("CU04: falha ao consultar os leilões atuais do item %s no banco de dados", item_id)
        raise HTTPException(status_code=503, detail=mensagens.FALHA_NO_HISTORICO) from e
