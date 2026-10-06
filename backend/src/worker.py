import os
import threading
import time
from datetime import datetime, timedelta, timezone
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

# Agendador em uso (definido em start_scheduler); a ingestão de mercado reagenda a si mesma depois de cada rodada.
scheduler = None
INGESTAO_JOB_ID = "ingestao_job"
VIGIA_JOB_ID = "vigia_ingestao_job"

# A rodada é quem agenda a seguinte. O APScheduler descarta um job `date` atrasado além da tolerância, e então ninguém
# agendava mais nada: com o PC suspenso por dias (Docker pausado), a coleta horária parava para sempre e só o job da Ficha
# seguia vivo. Por isso a rodada nunca é descartada por atraso: ao acordar, ela roda na hora (e a recuperação de 48 h,
# que é decidida dentro dela, é avaliada).
ATRASO_MAXIMO_DA_RODADA = None
# De quanto em quanto tempo o vigia confere se existe uma rodada agendada (defesa para qualquer outra forma de a cadeia se perder).
INTERVALO_DO_VIGIA_MINUTOS = 5
# Trava da rodada em andamento: um job `date` sai do agendador ao começar a rodar, então sem ela o vigia não distinguiria
# "a cadeia se perdeu" de "a rodada está executando agora".
_rodada_em_andamento = threading.Lock()

# ITEM_IDS agora são dinâmicos através da tabela Item

def job_fetch_wow_token_price():
    """Ficha do WoW (item 122284): a única rotina a cada 15 minutos. Não pertence a nenhum caso de uso detalhado."""
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

def job_preencher_itens_novos():
    """CU09-C3-FA1: itens cadastrados pela ingestão nascem com nome provisório ("Item {id}"); completa o nome e o
    ícone pela API de dados do jogo da Blizzard (a mesma rotina da sincronização diária)."""
    from src.scraper.populate_item_details import populate_details
    populate_details()

def job_run_backfill():
    """CU10-C1: recupera o histórico pelos .bin da Undermine Exchange (importação incremental dos itens ativos de cada
    reino monitorado). Só é chamado pela regra de recuperação (mais de 48 h sem nenhuma coleta), não mais de hora em
    hora."""
    logger.info(">>> Iniciando rotina de backfill de históricos...")
    from src.services.importacao_historico import ImportacaoHistoricoService
    session = get_session()
    try:
        ImportacaoHistoricoService(session).recuperar()
    except Exception as e:
        logger.error(f"Erro no job de backfill: {e}")
    finally:
        session.close()

def job_ingestao_de_mercado():
    """
    CU09-C1 (ativação): rodada de ingestão dos leilões da Blizzard, de 60 em 60 minutos. Ao iniciar o worker, a rodada
    roda na hora; ela decide sozinha se precisa recompor o histórico (mais de 48 h sem coleta) e quais endpoints já
    podem ser consultados (RN05). Ao terminar, agenda a próxima para quando o primeiro endpoint puder ser consultado,
    aconteça o que acontecer na rodada (senão a coleta pararia para sempre).
    """
    if not _rodada_em_andamento.acquire(blocking=False):
        logger.warning("Já há uma rodada de ingestão de mercado em andamento; esta foi ignorada.")
        return
    try:
        proximo = None
        try:
            proximo = _rodada_de_ingestao()
        except Exception:
            logger.exception("Erro na rodada de ingestão de mercado.")
        agendar_ingestao(proximo)
    finally:
        _rodada_em_andamento.release()

def _rodada_de_ingestao():
    """Executa uma rodada (`executar_rodada`) e devolve quando a próxima deve rodar (None: não foi possível calcular)."""
    from src.services.ingestao_config import carregar_mercados
    from src.services.rodada_de_ingestao import executar_rodada

    client_id = os.getenv("BLIZZARD_CLIENT_ID")
    client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("Env vars 'BLIZZARD_CLIENT_ID' ou 'BLIZZARD_CLIENT_SECRET' ausentes. Ingestão de mercado ignorada.")
        return None
    session = get_session()
    try:
        return executar_rodada(
            session, BlizzardApiClient(client_id, client_secret), carregar_mercados(), job_run_backfill,
            preencher_itens_novos=job_preencher_itens_novos,
        )
    finally:
        session.close()

def agendar_ingestao(quando=None):
    """Agenda a próxima rodada da ingestão de mercado. Sem horário (falha ou credenciais ausentes), tenta em 1 hora."""
    if scheduler is None:
        return
    if quando is None:
        quando = datetime.now(timezone.utc) + timedelta(hours=1)
    scheduler.add_job(
        job_ingestao_de_mercado, 'date', run_date=quando, id=INGESTAO_JOB_ID,
        replace_existing=True, misfire_grace_time=ATRASO_MAXIMO_DA_RODADA,
    )
    logger.info("Próxima rodada de ingestão de mercado agendada para %s.", quando.isoformat())

def job_vigiar_ingestao():
    """CU09-C1 (ativação): garante que a ingestão de mercado tenha sempre uma próxima rodada agendada. Se a cadeia de
    rodadas se perdeu (ninguém agendou a seguinte), retoma na hora; a rodada decide sozinha o que coletar (RN05, 48 h)."""
    if scheduler is None or _rodada_em_andamento.locked() or scheduler.get_job(INGESTAO_JOB_ID) is not None:
        return
    logger.warning("Nenhuma rodada de ingestão de mercado agendada; retomando agora.")
    agendar_ingestao(datetime.now(timezone.utc))

def start_scheduler():
    global scheduler
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

    now_local = datetime.now()
    scheduler = BackgroundScheduler()

    # Agenda a Ficha do WoW a cada 15 minutos (começando agora). É a ÚNICA rotina nesse intervalo.
    scheduler.add_job(job_fetch_wow_token_price, 'interval', minutes=15, id='token_job', next_run_time=now_local)

    # Agenda a descoberta de novos itens a cada 24 horas
    scheduler.add_job(job_sync_items, 'interval', days=1, id='sync_items_job')

    # Ingestão de mercado (CU09): roda na hora ao iniciar e reagenda a si mesma de 60 em 60 minutos; o vigia a retoma
    # se a cadeia se perder.
    agendar_ingestao(datetime.now(timezone.utc))
    scheduler.add_job(job_vigiar_ingestao, 'interval', minutes=INTERVALO_DO_VIGIA_MINUTOS, id=VIGIA_JOB_ID)

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
