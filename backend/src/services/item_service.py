from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import requests
from src.scraper.models import HistoricalItemPrice
from src.models.item import Item
from src.scraper.parser import decompress_and_parse

class ItemService:
    def __init__(self, session: Session):
        self.session = session

    def get_item_history(self, item_id: int, region: str = "US", window: str = "14D"):
        """
        Busca o histórico de preços e volumes de um item específico na janela de tempo especificada.
        """
        # Parse window
        days = 14
        if window == 'ALL':
            days = None
        elif window.endswith('D'):
            try:
                days = int(window[:-1])
            except ValueError:
                pass
        
        query = self.session.query(HistoricalItemPrice).filter(
            HistoricalItemPrice.item_id == item_id
        )
        
        if days is not None:
            # O backend trata tudo em UTC
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(HistoricalItemPrice.timestamp >= cutoff_date)
            
        query = query.order_by(HistoricalItemPrice.timestamp.asc())
        
        results = query.all()
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                "timestamp": r.timestamp.isoformat(),
                "price": r.price,
                "quantity": r.quantity
            })
            
        return formatted_results

    def search_items(self, query: str, limit: int = 10):
        """
        Busca itens pelo nome (case-insensitive).
        """
        if not query or len(query) < 2:
            return []
            
        items = self.session.query(Item).filter(
            Item.name.ilike(f"%{query}%")
        ).limit(limit).all()
        
        return [
            {"id": item.external_item_id, "name": item.name, "icon_url": item.icon_url} 
            for item in items
        ]

    def get_current_auctions(self, item_id: int, region: str = "3209"):
        """
        Busca os leilões atuais do item em tempo real via The Undermine Exchange.
        """
        bucket_id = int(item_id) & 255
        urls_to_try = [f"https://undermine.exchange/data/{region}/{bucket_id}/{item_id}.bin"]
        if region != "32512":
            urls_to_try.append(f"https://undermine.exchange/data/32512/{bucket_id}/{item_id}.bin")
            
        headers = {
            'User-Agent': 'GoblinLedger/1.0 (Live Fetch)',
            'Accept': '*/*'
        }
        
        for url in urls_to_try:
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                parsed_data = decompress_and_parse(response.content)
                
                auctions = parsed_data.get('auctions', [])
                if not auctions:
                    return {"min_price": 0, "total_quantity": 0}
                    
                min_price = min(auc['price'] for auc in auctions)
                total_quantity = sum(auc['quantity'] for auc in auctions)
                
                return {
                    "min_price": min_price,
                    "total_quantity": total_quantity
                }
            except Exception as e:
                pass
                
        return {"min_price": 0, "total_quantity": 0}
