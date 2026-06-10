import os
import time
from datetime import datetime
import logging
from dotenv import load_dotenv
import sys
from apscheduler.schedulers.blocking import BlockingScheduler

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

# ITEM_IDS agora são dinâmicos através da tabela Item

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
        from src.models.item import Item
        from src.scraper.sync_items import sync_items_from_blizzard
        
        # Auto-Bootstrap Logic
        count = session.query(Item).count()
        if count == 0:
            logger.info("Banco Item vazio. Iniciando Auto-Bootstrap...")
            sync_items_from_blizzard()
            
        # Puxa itens dinamicamente
        active_items = session.query(Item.external_item_id).filter(
            Item.game == 'wow',
            Item.is_active == True
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

def job_run_backfill():
    logger.info(">>> Iniciando rotina de backfill de históricos...")
    from src.scraper.backfill import run_backfill, get_items_to_process
    session = get_session()
    try:
        items = get_items_to_process(session)
        if items:
            run_backfill(session, items, "3209")
        else:
            logger.info("Nenhum item para backfill.")
    except Exception as e:
        logger.error(f"Erro no job de backfill: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    load_dotenv()
    
    logger.info("====================================")
    logger.info("Iniciando Goblin Ledger Worker (APScheduler)...")
    logger.info("====================================")

    # Garante criacao inicial
    init_db()

    scheduler = BlockingScheduler()

    # Agenda a Ficha do WoW a cada 15 minutos (começando agora)
    scheduler.add_job(job_fetch_wow_token_price, 'interval', minutes=15, id='token_job', next_run_time=datetime.now())
    
    # Agenda o Backfill a cada 6 horas (começando agora)
    scheduler.add_job(job_run_backfill, 'interval', hours=6, id='backfill_job', next_run_time=datetime.now())
    
    logger.info("Scheduler rodando. Pressione Ctrl+C para sair.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker encerrado.")
