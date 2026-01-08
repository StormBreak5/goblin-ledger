from sqlalchemy.orm import Session
from database import SessionLocal, MarketHistory
from sqlalchemy import func

import json
import os

class AuctionService:
    def __init__(self):
        self.db = SessionLocal()
    
    def get_all_auctions(self, limit: int = 100):
        return self.db.query(MarketHistory).order_by(MarketHistory.captured_at.desc()).limit(limit).all()
        
    def get_stats(self):
        try:
            total_items = self.db.query(MarketHistory).count()
            avg_price = self.db.query(func.avg(MarketHistory.price)).scalar() or 0
            
            return {
                "total_records": total_items,
                "average_price_copper": round(avg_price, 2),
                "message": "Dados vindos do PostgreSQL em tempo real"
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            self.db.close()
        