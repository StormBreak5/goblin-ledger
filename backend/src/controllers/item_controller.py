from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.repositories.database import get_session
from src.services.item_service import ItemService

router = APIRouter(tags=["items"])

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/items/{item_id}/history")
def get_item_history(
    item_id: int, 
    window: str = Query("14D", description="Janela de tempo para o histórico (ex: 7D, 14D)"),
    db: Session = Depends(get_db)
):
    """
    Recupera o histórico de preços e volumes de um item específico na Casa de Leilões.
    """
    try:
        service = ItemService(db)
        history = service.get_item_history(item_id=item_id, window=window)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
