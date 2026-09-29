import os
import time
from datetime import datetime
import logging
from dotenv import load_dotenv
import sys
from apscheduler.schedulers.background import BackgroundScheduler

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
        # Recupera dado do token oficial (o Worker no MVP roda baseado na blizzard)
        token_data = api_client.get_wow_token_price(region="us")
        
        # Salva o preco exclusivo para a Ficha do WoW (ID: 122284)
        repo.save_price(item_id=122284, region="us", token_response=token_data)
        
    except Exception as e:
        logger.error(f"Ocorreu um erro recuperando ou salvando a ficha: {e}")
    finally:
        session.close()

def job_sync_items():
    logger.info(">>> Iniciando sincronizacao de itens na base de dados (Auto-Discovery)...")
    try:
        from src.scraper.sync_items import sync_items_from_blizzard
        sync_items_from_blizzard()
    except Exception as e:
        logger.error(f"Erro na sincronizacao de itens: {e}")

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

def start_scheduler():
    logger.info("====================================")
    logger.info("Iniciando Goblin Ledger Worker (APScheduler Background)...")
    logger.info("====================================")

    # Garante criacao inicial
    init_db()

    # Auto-Bootstrap Logic
    session = get_session()
    try:
        from src.models.item import Item
        count = session.query(Item).count()
        if count == 0:
            logger.info("Banco Item vazio. Iniciando Auto-Bootstrap...")
            from src.scraper.sync_items import sync_items_from_blizzard
            sync_items_from_blizzard()
    except Exception as e:
        logger.error(f"Erro no Auto-Bootstrap: {e}")
    finally:
        session.close()

    # Puxa o último log de execução para decidir a hora do próximo Backfill
    session = get_session()
    from src.scraper.models import ScraperExecutionLog, ExecutionStatus
    from datetime import timedelta
    
    last_log = session.query(ScraperExecutionLog).filter(
        ScraperExecutionLog.status == ExecutionStatus.SUCCESS
    ).order_by(ScraperExecutionLog.execution_start.desc()).first()
    session.close()

    now_utc = datetime.utcnow()
    now_local = datetime.now()
    backfill_next_run = now_local

    if last_log and last_log.execution_start:
        time_since_last_run = now_utc - last_log.execution_start
        if time_since_last_run > timedelta(hours=1):
            backfill_next_run = now_local # Roda imediatamente
        else:
            backfill_next_run = now_local + (timedelta(hours=1) - time_since_last_run)

    scheduler = BackgroundScheduler()

    # Agenda a Ficha do WoW a cada 15 minutos (começando agora)
    scheduler.add_job(job_fetch_wow_token_price, 'interval', minutes=15, id='token_job', next_run_time=now_local)
    
    # Agenda o Backfill a cada 1 hora 
    scheduler.add_job(job_run_backfill, 'interval', hours=1, id='backfill_job', next_run_time=backfill_next_run)

    # Agenda a descoberta de novos itens a cada 24 horas
    scheduler.add_job(job_sync_items, 'interval', days=1, id='sync_items_job')
    
    scheduler.start()
    logger.info("Scheduler rodando em background.")
    return scheduler

if __name__ == "__main__":
    load_dotenv()
    scheduler = start_scheduler()
    try:
        # Impede que a thread principal termine
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Worker encerrado.")
