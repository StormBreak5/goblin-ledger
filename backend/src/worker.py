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

# Parseia IDs de itens separados por vírgula no ENV, joga o WoW Token de fallback
ITEMS_TO_TRACK = os.getenv("ITEMS_TO_TRACK", "122284")
ITEM_IDS = [int(x.strip()) for x in ITEMS_TO_TRACK.split(",") if x.strip().isdigit()]

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
        # Recupera dado
        # Edge Case 1 & 2: requests já vai levantar exception de fallback HTTP de downtime, que capturaos aqui
        token_data = api_client.get_wow_token_price(region="us")
        
        for item_id in ITEM_IDS:
            # Atualmente a lógica da BlizzardApiClient.get_wow_token_price foca exclusivamente 
            # no endpoint do token. Para extrapolar a outros item_ids, ela precisaria
            # bater na API genérica de leilão ou commodities.
            # Como a spec pede focar no WoW token, faremos o insert baseado no id extraído.
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
