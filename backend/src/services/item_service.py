from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from src.scraper.models import HistoricalItemPrice

class ItemService:
    def __init__(self, session: Session):
        self.session = session

    def get_item_history(self, item_id: int, region: str = "US", window: str = "14D"):
        """
        Busca o histórico de preços e volumes de um item específico na janela de tempo especificada.
        """
        # Parse window
        days = 14
        if window.endswith('D'):
            try:
                days = int(window[:-1])
            except ValueError:
                pass
        
        # O backend trata tudo em UTC
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # O Provider padronizou a região US_COMMODITY_CONNECTED_ID = "32512" 
        # mas na tabela ele salva como a region string ou id. No backfill salva como string ex: '32512'
        # Aqui simplificaremos assumindo a query por item_id e ignorando region por enquanto, 
        # ou tratando caso haja múltiplos.
        
        query = self.session.query(HistoricalItemPrice).filter(
            HistoricalItemPrice.item_id == item_id,
            HistoricalItemPrice.timestamp >= cutoff_date
        ).order_by(HistoricalItemPrice.timestamp.asc())
        
        results = query.all()
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                "timestamp": r.timestamp.isoformat(),
                "price": r.price,
                "quantity": r.quantity
            })
            
        return formatted_results
