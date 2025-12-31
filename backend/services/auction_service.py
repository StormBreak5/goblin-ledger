import json
import os

class AuctionService:
    def get_all_auctions(self):
        
        try:
            file_path = os.path.join(os.getcwd(), 'data', 'mock_auctions.json')

            with open(file_path, 'r') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            return []
        
    def get_stats(self):
        data = self.get_all_auctions()
        if not data:
            return {"total_items": 0, "market_cap_gold": 0}

        total_gold = sum(item['buyout'] for item in data) / 10000
        return{
            "total_items": len(data),
            "market_cap_gold": total_gold
        }
        