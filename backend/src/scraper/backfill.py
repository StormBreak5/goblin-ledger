import argparse
import sys
import logging
import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Any, Dict, Optional

from psycopg2.extras import execute_values
from sqlalchemy.orm import Session
from sqlalchemy import func, update

import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog, ExecutionStatus
from src.scraper.parser import decompress_and_parse
from src.models.item import Item

logger = logging.getLogger(__name__)

# Configuration variables (can be overridden by args)
MAX_CONCURRENT_REQUESTS = 50
REQUEST_DELAY_SECONDS = 0.05
US_COMMODITY_CONNECTED_ID = "32512"  # Undermine Exchange ID for US regional commodities
WOW_TOKEN_ID = 122284
TOKEN_SOURCE = "global"
TOKEN_URL = "https://undermine.exchange/data/global/token-us.bin"

# CU10-C1: o histórico é baixado e gravado em lotes, dentro de uma única transação.
CHUNK_SIZE = 500  # itens baixados antes de cada gravação (limita a memória usada)
INSERT_PAGE_SIZE = 10_000  # linhas por INSERT
# CU10-C1 passo 8: só chegam ao banco os pontos mais novos que o último já gravado do item. A margem cobre
# o agregado diário do dia corrente, que só é finalizado (com data 00:00) depois de já existirem snapshots do dia.
INCREMENTAL_LOOKBACK = timedelta(days=2)
# CU10-C1 passo 7: pontos com data fora deste intervalo são registros inconsistentes e são descartados
# (o limite inferior é anterior ao lançamento do jogo; a tolerância no futuro cobre diferenças de relógio).
MIN_VALID_TIMESTAMP = datetime(2004, 1, 1)
FUTURE_TOLERANCE = timedelta(days=1)

INSERT_SQL = (
    f"INSERT INTO {HistoricalItemPrice.__tablename__} (item_id, region, timestamp, price, quantity) VALUES %s "
    "ON CONFLICT (item_id, region, timestamp) DO NOTHING"
)


@dataclass
class BackfillTarget:
    """Dados do item lidos do ORM antes do download, para não tocar a sessão em outra thread nem
    disparar um SELECT por atributo expirado a cada item."""
    pk: Any  # Item.id
    item_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def last_etag(self) -> Optional[str]:
        return self.metadata.get('last_etag')

    @property
    def source_region(self) -> Optional[str]:
        return self.metadata.get('source_region')


def get_items_to_process(session: Session) -> List[Item]:
    """
    Retrieves the list of active tracked items from the database.
    """
    return session.query(Item).filter(
        Item.game == 'wow',
        Item.is_active == True
    ).all()


def candidate_urls(item_id: int, region_id: str, preferred_source: Optional[str] = None) -> List[Tuple[str, str]]:
    """CU10-C1 passo 3: URLs do arquivo do item, como (origem, url). A origem que já atendeu o item vem primeiro,
    evitando a requisição que daria 404 (reino local) nos itens de commodity."""
    if item_id == WOW_TOKEN_ID:
        return [(TOKEN_SOURCE, TOKEN_URL)]

    bucket_id = item_id & 255
    sources = [region_id]
    if region_id != US_COMMODITY_CONNECTED_ID:
        sources.append(US_COMMODITY_CONNECTED_ID)
    if preferred_source in sources:
        sources.remove(preferred_source)
        sources.insert(0, preferred_source)
    return [(source, f'https://undermine.exchange/data/{source}/{bucket_id}/{item_id}.bin') for source in sources]


async def fetch_item_history(
    session: aiohttp.ClientSession, region_id: str, target: BackfillTarget
) -> Tuple[int, Any, Optional[str], Optional[str], Optional[str]]:
    """Fetch item history, returning (status_code, parsed_data, new_etag, error_msg, source)"""

    headers = {
        'User-Agent': 'GoblinLedger/1.0 (Backfill Bot)',
        'Accept-Encoding': 'gzip, deflate, br'
    }

    last_etag = target.last_etag
    if last_etag:
        headers['If-None-Match'] = last_etag

    for source, url in candidate_urls(target.item_id, region_id, target.source_region):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 304:
                    return 304, None, last_etag, None, source

                if response.status == 200:
                    new_etag = response.headers.get('ETag')
                    data = await response.read()
                    parsed_data = decompress_and_parse(data)
                    return 200, parsed_data, new_etag, None, source

                if response.status == 429:
                    return 429, None, last_etag, "Rate Limit (429)", None

                if response.status == 404:
                    continue # Try the next URL (commodity fallback)

                return response.status, None, last_etag, f"HTTP {response.status}", None

        except Exception as e:
            return 0, None, last_etag, str(e), None

    # If every URL failed with 404
    return 404, None, last_etag, "HTTP 404", None


async def worker(target: BackfillTarget, region_id: str, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, results: list):
    """Worker task to process a single item."""
    async with semaphore:
        status, data, new_etag, error, source = await fetch_item_history(session, region_id, target)

        results.append({
            'target': target,
            'status': status,
            'data': data,
            'new_etag': new_etag,
            'error': error,
            'source': source
        })

        if status == 200:
            logger.info(f"Downloaded new data for item {target.item_id}")
        elif status == 304:
            logger.debug(f"Item {target.item_id} not modified (304)")
        elif status == 429:
            logger.warning(f"Rate limited on item {target.item_id}")
        else:
            logger.warning(f"Error fetching item {target.item_id}: {error}")

        await asyncio.sleep(REQUEST_DELAY_SECONDS)


def load_last_seen(session: Session, region_id: str) -> Dict[int, datetime]:
    """CU10-C1 passo 8: data (UTC) do último ponto já gravado de cada item na região."""
    rows = (
        session.query(HistoricalItemPrice.item_id, func.max(HistoricalItemPrice.timestamp))
        .filter(HistoricalItemPrice.region == region_id)
        .group_by(HistoricalItemPrice.item_id)
        .all()
    )
    return {item_id: last for item_id, last in rows}


def _insert_rows(db_session: Session, rows: List[tuple]) -> int:
    """CU10-C1 passo 9: grava as linhas em páginas, ignorando as já existentes. Devolve quantas foram inseridas."""
    if not rows:
        return 0
    cursor = db_session.connection().connection.cursor()
    try:
        inserted = 0
        for start in range(0, len(rows), INSERT_PAGE_SIZE):
            page = rows[start:start + INSERT_PAGE_SIZE]
            execute_values(cursor, INSERT_SQL, page, page_size=len(page))
            inserted += cursor.rowcount
        return inserted
    finally:
        cursor.close()


class ChunkWriter:
    """
    CU10-C1 passos 5 a 9: converte e grava cada lote de itens baixados. Tudo é gravado na transação aberta da
    sessão, que só é confirmada no fim; se qualquer lote falhar, a importação inteira é desfeita (CU10-C1-FE2).
    """

    def __init__(self, db_session: Session, region_id: str, last_seen: Dict[int, datetime]):
        self.db_session = db_session
        self.region_id = region_id
        self.last_seen = last_seen
        self.items_processed = 0
        self.records_inserted = 0
        self.records_discarded = 0
        self.write_seconds = 0.0

    def __call__(self, results: list) -> None:
        started = time.monotonic()
        rows: List[tuple] = []
        items_to_update = []
        discarded = 0
        latest_valid = datetime.now(timezone.utc).replace(tzinfo=None) + FUTURE_TOLERANCE

        for r in results:
            target: BackfillTarget = r['target']
            self.items_processed += 1

            if r['status'] == 200 and r['data']:
                last = self.last_seen.get(target.item_id)
                cutoff = last - INCREMENTAL_LOOKBACK if last is not None else None

                # Combine snapshots and daily into one list of points
                points = r['data'].get('snapshots', []) + r['data'].get('daily', [])
                for p in points:
                    try:
                        # Convert timestamp from ms to datetime
                        timestamp = datetime.fromtimestamp(p['snapshot'] / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                    except (ValueError, OverflowError, OSError):
                        discarded += 1
                        continue
                    # CU10-C1 passo 7: no Linux uma data absurda converte sem erro e não pode chegar ao banco
                    # (nem virar o "último ponto" do item, que alimenta o filtro incremental).
                    if not MIN_VALID_TIMESTAMP <= timestamp <= latest_valid:
                        discarded += 1
                        continue
                    if cutoff is not None and timestamp <= cutoff:
                        continue
                    rows.append((target.item_id, self.region_id, timestamp, p['price'], p['quantity']))

                # Update item's ETag and remember which source served it
                new_meta = dict(target.metadata)
                new_meta['last_etag'] = r['new_etag']
                new_meta['source_region'] = r['source']
                items_to_update.append({'id': target.pk, 'metadata_info': new_meta})

        self.records_inserted += _insert_rows(self.db_session, rows)
        if items_to_update:
            self.db_session.execute(update(Item), items_to_update)

        self.records_discarded += discarded
        if discarded:
            logger.warning(f"Chunk had {discarded} price points with an invalid date; discarded (CU10-C1 step 7).")
        self.write_seconds += time.monotonic() - started
        logger.info(f"Chunk saved: {len(results)} items, {len(rows)} price points sent ({self.records_inserted} inserted so far).")


async def run_backfill_async(targets: List[BackfillTarget], region_id: str, on_chunk) -> float:
    """Baixa os itens em lotes e entrega cada lote a `on_chunk` (executado numa thread, enquanto o lote seguinte
    é baixado). Devolve o tempo gasto no download e na decodificação. O ritmo de requisições não muda."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    loop = asyncio.get_running_loop()
    download_seconds = 0.0
    pending_write = None

    async with aiohttp.ClientSession() as session:
        for start in range(0, len(targets), CHUNK_SIZE):
            results: list = []
            started = time.monotonic()
            await asyncio.gather(*[
                worker(target, region_id, semaphore, session, results)
                for target in targets[start:start + CHUNK_SIZE]
            ])
            download_seconds += time.monotonic() - started

            if pending_write is not None:
                await pending_write  # falha na gravação do lote anterior interrompe a importação
            pending_write = loop.run_in_executor(None, on_chunk, results)

        if pending_write is not None:
            await pending_write

    return download_seconds


def run_backfill(session: Session, items: List[Item], region: str):
    # Lê tudo o que precisa dos itens antes do primeiro commit (que expira os atributos do ORM).
    targets = [
        BackfillTarget(pk=item.id, item_id=int(item.external_item_id), metadata=dict(item.metadata_info or {}))
        for item in items
    ]

    log = ScraperExecutionLog(
        execution_start=datetime.utcnow(),
        status=ExecutionStatus.RUNNING,
        items_processed=0,
        records_inserted=0
    )
    session.add(log)
    session.commit()

    started = time.monotonic()
    try:
        writer = ChunkWriter(session, region, load_last_seen(session, region))

        # Download and save in chunks; nothing is committed until every chunk has been written.
        download_seconds = asyncio.run(run_backfill_async(targets, region, writer))

        log.items_processed = writer.items_processed
        log.records_inserted = writer.records_inserted
        log.status = ExecutionStatus.SUCCESS
        log.execution_end = datetime.utcnow()
        session.commit()

        logger.info(
            f"Backfill finished. Processed {writer.items_processed} items. Inserted {writer.records_inserted} new price points, discarded {writer.records_discarded} invalid ones. "
            f"Timings: download+decode={download_seconds:.1f}s, write={writer.write_seconds:.1f}s, total={time.monotonic() - started:.1f}s."
        )

    except KeyboardInterrupt:
        logger.warning("Backfill interrupted by user.")
        session.rollback()
        log.status = ExecutionStatus.FAILED
        log.error_message = "KeyboardInterrupt"
        log.execution_end = datetime.utcnow()
        session.commit()
        sys.exit(1)

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"Backfill failed: {e}\n{traceback_str}")
        session.rollback()  # CU10-C1-FE2: sem registros parciais
        log.status = ExecutionStatus.FAILED
        log.error_message = str(e)
        log.execution_end = datetime.utcnow()
        session.commit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Run historical price backfill using aiohttp.")
    parser.add_argument("--connected-id", type=str, default="3209", help="Connected Realm ID (default: 3209 = Azralon). Commodities fallback to 32512 automatically.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of items to backfill (useful for quick presentations)")
    args = parser.parse_args()

    from src.repositories.database import init_db, get_session
    from dotenv import load_dotenv

    load_dotenv()
    init_db()

    session = get_session()
    items = get_items_to_process(session)

    if args.limit:
        items = items[:args.limit]
        logger.info(f"Limiting backfill to {args.limit} items due to --limit argument")

    logger.info(f"Starting async backfill for {len(items)} items on Connected ID {args.connected_id}")

    try:
        if len(items) > 0:
            run_backfill(session, items, args.connected_id)
        else:
            logger.info("No active items found. Please run bootstrap first.")
    finally:
        session.close()
