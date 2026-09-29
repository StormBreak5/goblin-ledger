import sys
import os
import requests

# Mock parser
def decompress_and_parse(content):
    import gzip
    import json
    # No, wait, parser.py does it! Let's import parser.py
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.scraper.parser import decompress_and_parse
    return decompress_and_parse(content)

def get_current_auctions(item_id: int, region: str = "3209"):
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
            print(f"Trying {url}")
            response = requests.get(url, headers=headers, timeout=5)
            print(f"Status: {response.status_code}")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            parsed_data = decompress_and_parse(response.content)
            
            auctions = parsed_data.get('auctions', [])
            print(f"Auctions found: {len(auctions)}")
            if not auctions:
                return {"min_price": 0, "total_quantity": 0}
                
            min_price = min(auc['price'] for auc in auctions)
            total_quantity = sum(auc['quantity'] for auc in auctions)
            
            return {
                "min_price": min_price,
                "total_quantity": total_quantity
            }
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            print(traceback.format_exc())
            pass
            
    return {"min_price": 0, "total_quantity": 0}

if __name__ == "__main__":
    print(get_current_auctions(122284))
