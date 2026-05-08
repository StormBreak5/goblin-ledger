import os
import time
import logging
from dotenv import load_dotenv
import sys

# Corrige imports quando rodando direto.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.database import init_db, get_session
from src.services.api_client import BlizzardApiClient
from src.repositories.item_price_repository import ItemPriceRepository

# Setup Básico de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ITEM_IDS agora são dinâmicos através da tabela TrackedItem

def job_fetch_wow_token_price():
    client_id = os.getenv("BLIZZARD_CLIENT_ID")
    client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error("Env vars 'BLIZZARD_CLIENT_ID' ou 'BLIZZARD_CLIENT_SECRET' ausentes. Pulando job.")
        return

    # Inicia dependencias do Job
    api_client = BlizzardApiClient(client_id, client_secret)
    session = get_session()
    repo = ItemPriceRepository(session)

    try:
        from src.models.tracked_item import TrackedItem
        from src.scraper.sync_tracked_items import sync_items_from_blizzard
        
        # Auto-Bootstrap Logic
        count = session.query(TrackedItem).count()
        if count == 0:
            logger.info("Banco TrackedItem vazio. Iniciando Auto-Bootstrap...")
            sync_items_from_blizzard()
            
        # Puxa itens dinamicamente
        active_items = session.query(TrackedItem.external_item_id).filter(
            TrackedItem.game == 'wow',
            TrackedItem.is_active == True
        ).all()
        
        item_ids = [int(it[0]) for it in active_items]
        
        # Recupera dado do token oficial (o Worker no MVP roda baseado na blizzard)
        token_data = api_client.get_wow_token_price(region="us")
        
        for item_id in item_ids:
            # O comportamento anterior salvava token para todos.
            repo.save_price(item_id=item_id, region="us", token_response=token_data)
        
    except Exception as e:
        logger.error(f"Ocorreu um erro recuperando ou salvando a ficha: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    load_dotenv()
    
    logger.info("====================================")
    logger.info("Iniciando Goblin Ledger Worker...")
    logger.info("====================================")

    # Garante criacao inicial
    init_db()

    # Tempo padrao de wait: 15 minutos em segundos (15 * 60 = 900)
    poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", 900))

    while True:
        logger.info(">>> Iniciando varredura...")
        job_fetch_wow_token_price()
        
        logger.info(f"Dormindo por {poll_interval_seconds} segundos...")
        time.sleep(poll_interval_seconds)
