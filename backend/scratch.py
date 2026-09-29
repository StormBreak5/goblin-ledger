import os
import sys
import json
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.services.api_client import BlizzardApiClient

load_dotenv()
client = BlizzardApiClient(os.getenv("BLIZZARD_CLIENT_ID"), os.getenv("BLIZZARD_CLIENT_SECRET"))
token = client.auth_manager.get_token()

import requests
url = f"https://us.api.blizzard.com/data/wow/connected-realm/11/auctions?namespace=dynamic-us&locale=en_US"
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    auctions = data.get("auctions", [])
    unique_items = set(a.get("item", {}).get("id") for a in auctions)
    print(f"Total auctions: {len(auctions)}")
    print(f"Unique items: {len(unique_items)}")
else:
    print(response.status_code, response.text)
