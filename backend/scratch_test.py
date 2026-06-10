import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.scraper.parser import decompress_and_parse

def get_current_auctions(item_id: int, region: str = "32512"):
    bucket_id = int(item_id) & 255
    url = f"https://undermine.exchange/data/{region}/{bucket_id}/{item_id}.bin"
    headers = {
        'User-Agent': 'GoblinLedger/1.0 (Live Fetch)',
        'Accept': '*/*'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        parsed_data = decompress_and_parse(response.content)
        
        auctions = parsed_data.get('auctions', [])
        if not auctions:
            return {"min_price": 0, "total_quantity": 0, "error": "No auctions found"}
            
        min_price = min(auc['price'] for auc in auctions)
        total_quantity = sum(auc['quantity'] for auc in auctions)
        
        return {
            "min_price": min_price,
            "total_quantity": total_quantity
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

if __name__ == "__main__":
    print(get_current_auctions(122284))
