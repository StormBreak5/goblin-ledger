import os
import sys
import logging
import asyncio
import aiohttp
from typing import List
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.repositories.database import init_db, get_session
from src.services.api_client import BlizzardApiClient
from src.models.item import Item
from sqlalchemy.orm import Session
from sqlalchemy import update

logger = logging.getLogger(__name__)

MAX_CONCURRENT_REQUESTS = 10

async def fetch_item_details(session: aiohttp.ClientSession, item_id: int, token: str, region: str = "us"):
    """
    Fetches the item's name and icon_url from the Blizzard API asynchronously.
    """
    namespace = f"static-{region}"
    locale = "en_US" if region == "us" else "en_GB"
    headers = {"Authorization": f"Bearer {token}"}
    
    item_url = f"https://{region}.api.blizzard.com/data/wow/item/{item_id}?namespace={namespace}&locale={locale}"
    media_url = f"https://{region}.api.blizzard.com/data/wow/media/item/{item_id}?namespace={namespace}&locale={locale}"
    
    name = None
    icon_url = None
    
    try:
        # Fetch Name
        async with session.get(item_url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                # O nome pode vir como um objeto com traduções ou direto dependendo do endpoint/locale
                if isinstance(data.get("name"), dict):
                    name = data["name"].get("en_US")
                else:
                    name = data.get("name")
                    
        # Fetch Media (Icon)
        async with session.get(media_url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("assets", [])
                for asset in assets:
                    if asset.get("key") == "icon":
                        icon_url = asset.get("value")
                        break
                        
        return item_id, name, icon_url
        
    except Exception as e:
        logger.error(f"Error fetching details for item {item_id}: {e}")
        return item_id, None, None

async def worker(item: Item, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, token: str, results: list):
    async with semaphore:
        item_id = int(item.external_item_id)
        _, name, icon_url = await fetch_item_details(session, item_id, token)
        
        if name or icon_url:
            results.append({
                "id": item.id,
                "name": name if name else item.name,
                "icon_url": icon_url
            })
            logger.info(f"Fetched details for {item_id}: {name}")
        else:
            logger.debug(f"Could not fetch details for {item_id}")
            
        await asyncio.sleep(0.1) # Small delay to avoid hammering the API too hard

async def run_population_async(items: List[Item], token: str) -> list:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    results = []
    
    async with aiohttp.ClientSession() as session:
        tasks = [worker(item, semaphore, session, token, results) for item in items]
        await asyncio.gather(*tasks)
        
    return results

def populate_details():
    logger.info("Iniciando população de detalhes dos itens (nomes e ícones)...")
    
    client_id = os.getenv("BLIZZARD_CLIENT_ID")
    client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error("Credenciais da Blizzard ausentes. População cancelada.")
        return

    api_client = BlizzardApiClient(client_id, client_secret)
    token = api_client.auth_manager.get_token()
    
    db_session = get_session()
    
    try:
        # Pega itens cujo nome começa com "Item " ou não têm icon_url
        items_to_update = db_session.query(Item).filter(
            (Item.name.like("Item %")) | (Item.icon_url == None)
        ).all()
        
        logger.info(f"Encontrados {len(items_to_update)} itens para atualizar.")
        
        if not items_to_update:
            return
            
        # Para evitar estourar limites se houver 15k, processamos em lotes de 1000
        chunk_size = 1000
        for i in range(0, len(items_to_update), chunk_size):
            chunk = items_to_update[i:i+chunk_size]
            logger.info(f"Processando lote {i//chunk_size + 1} de {len(items_to_update)//chunk_size + 1}...")
            
            results = asyncio.run(run_population_async(chunk, token))
            
            if results:
                # Update em batch
                db_session.execute(update(Item), results)
                db_session.commit()
                logger.info(f"Atualizados {len(results)} itens no banco de dados.")
                
    except Exception as e:
        logger.error(f"Erro ao popular detalhes dos itens: {e}")
        db_session.rollback()
    finally:
        db_session.close()
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    load_dotenv()
    init_db()
    populate_details()
