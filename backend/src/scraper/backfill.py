import argparse
import sys
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import List, Tuple, Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import update

import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog, ExecutionStatus
from src.scraper.parser import decompress_and_parse
from src.models.item import Item

logger = logging.getLogger(__name__)

# Constants
MAX_CONCURRENT_REQUESTS = 5
REQUEST_DELAY_SECONDS = 0.5
US_COMMODITY_CONNECTED_ID = "32512"  # Undermine Exchange ID for US regional commodities

def get_items_to_process(session: Session) -> List[Item]:
    """
    Retrieves the list of active tracked items from the database.
    """
    return session.query(Item).filter(
        Item.game == 'wow',
        Item.is_active == True
    ).all()

async def fetch_item_history(session: aiohttp.ClientSession, region_id: str, item: Item, last_etag: str = None) -> Tuple[int, Any, str, str]:
    """Fetch item history, returning (status_code, parsed_data, new_etag, error_msg)"""
    
    item_id = int(item.external_item_id)
    bucket_id = item_id & 255
    
    headers = {
        'User-Agent': 'GoblinLedger/1.0 (Backfill Bot)',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    
    if last_etag:
        headers['If-None-Match'] = last_etag
        
    # Special route for WoW Token
    if str(item_id) == "122284":
        urls_to_try = ['https://undermine.exchange/data/global/token-us.bin']
    else:
        # Try local realm first, if 404, fallback to regional commodities
        urls_to_try = [
            f'https://undermine.exchange/data/{region_id}/{bucket_id}/{item_id}.bin',
        ]
        if region_id != US_COMMODITY_CONNECTED_ID:
            urls_to_try.append(f'https://undermine.exchange/data/{US_COMMODITY_CONNECTED_ID}/{bucket_id}/{item_id}.bin')
    
    for url in urls_to_try:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 304:
                    return 304, None, last_etag, None
                    
                if response.status == 200:
                    new_etag = response.headers.get('ETag')
                    data = await response.read()
                    parsed_data = decompress_and_parse(data)
                    return 200, parsed_data, new_etag, None
                    
                if response.status == 429:
                    return 429, None, last_etag, "Rate Limit (429)"
                    
                if response.status == 404:
                    continue # Try the next URL (commodity fallback)
                    
                return response.status, None, last_etag, f"HTTP {response.status}"
                
        except Exception as e:
            return 0, None, last_etag, str(e)
            
    # If both failed with 404
    return 404, None, last_etag, "HTTP 404"


async def worker(item: Item, region_id: str, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, results: list):
    """Worker task to process a single item."""
    async with semaphore:
        last_etag = item.metadata_info.get('last_etag') if item.metadata_info else None
        status, data, new_etag, error = await fetch_item_history(session, region_id, item, last_etag)
        
        results.append({
            'item': item,
            'status': status,
            'data': data,
            'new_etag': new_etag,
            'error': error
        })
        
        if status == 200:
            logger.info(f"Downloaded new data for item {item.external_item_id}")
        elif status == 304:
            logger.debug(f"Item {item.external_item_id} not modified (304)")
        elif status == 429:
            logger.warning(f"Rate limited on item {item.external_item_id}")
        else:
            logger.warning(f"Error fetching item {item.external_item_id}: {error}")
            
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

async def run_backfill_async(items: List[Item], region_id: str) -> list:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    results = []
    
    async with aiohttp.ClientSession() as session:
        tasks = [worker(item, region_id, semaphore, session, results) for item in items]
        await asyncio.gather(*tasks)
        
    return results

def save_results(db_session: Session, results: list, region_id: str, log: ScraperExecutionLog):
    """Batch insert downloaded items to avoid memory/db overhead and update ETags."""
    total_inserted = 0
    items_processed = 0
    
    values_to_insert = []
    items_to_update = []
    
    for r in results:
        item = r['item']
        items_processed += 1
        
        if r['status'] == 200 and r['data']:
            # We got new data!
            parsed = r['data']
            
            # Combine snapshots and daily into one list of points
            points = parsed.get('snapshots', []) + parsed.get('daily', [])
            
            for p in points:
                try:
                    # Convert timestamp from ms to datetime
                    timestamp = datetime.fromtimestamp(p['snapshot'] / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                    values_to_insert.append({
                        "item_id": int(item.external_item_id),
                        "region": region_id,
                        "timestamp": timestamp,
                        "price": p['price'],
                        "quantity": p['quantity']
                    })
                except (ValueError, OverflowError, OSError) as e:
                    logger.warning(f"Invalid timestamp {p['snapshot']} for item {item.external_item_id}: {e}")
                    continue
                
            # Update item's ETag
            new_meta = dict(item.metadata_info) if item.metadata_info else {}
            new_meta['last_etag'] = r['new_etag']
            items_to_update.append({'id': item.id, 'metadata_info': new_meta})
            
    # Execute batch insert of historical prices
    if values_to_insert:
        logger.info(f"Batch inserting {len(values_to_insert)} price points...")
        stmt = insert(HistoricalItemPrice).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['item_id', 'region', 'timestamp']
        )
        result = db_session.execute(stmt)
        total_inserted += result.rowcount
        
    # Execute batch update of ETags
    if items_to_update:
        logger.info(f"Batch updating {len(items_to_update)} item ETags...")
        db_session.execute(update(Item), items_to_update)
        
    db_session.commit()
    
    log.items_processed = items_processed
    log.records_inserted = total_inserted
    log.status = ExecutionStatus.SUCCESS
    log.execution_end = datetime.utcnow()
    db_session.commit()
    
    logger.info(f"Backfill finished. Processed {items_processed} items. Inserted {total_inserted} new price points.")

def run_backfill(session: Session, items: List[Item], region: str):
    log = ScraperExecutionLog(
        execution_start=datetime.utcnow(),
        status=ExecutionStatus.RUNNING,
        items_processed=0,
        records_inserted=0
    )
    session.add(log)
    session.commit()
    
    try:
        # Run the async loop to download everything
        results = asyncio.run(run_backfill_async(items, region))
        
        # Save all results to the database synchronously
        save_results(session, results, region, log)
        
    except KeyboardInterrupt:
        logger.warning("Backfill interrupted by user.")
        log.status = ExecutionStatus.FAILED
        log.error_message = "KeyboardInterrupt"
        log.execution_end = datetime.utcnow()
        session.commit()
        sys.exit(1)
        
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"Backfill failed: {e}\n{traceback_str}")
        log.status = ExecutionStatus.FAILED
        log.error_message = str(e)
        log.execution_end = datetime.utcnow()
        session.commit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    parser = argparse.ArgumentParser(description="Run historical price backfill using aiohttp.")
    parser.add_argument("--connected-id", type=str, default="3209", help="Connected Realm ID (default: 3209 = Azralon). Commodities fallback to 32512 automatically.")
    args = parser.parse_args()
    
    from src.repositories.database import init_db, get_session
    from dotenv import load_dotenv
    
    load_dotenv()
    init_db()
    
    session = get_session()
    items = get_items_to_process(session)
    
    logger.info(f"Starting async backfill for {len(items)} items on Connected ID {args.connected_id}")
    
    try:
        if len(items) > 0:
            run_backfill(session, items, args.connected_id)
        else:
            logger.info("No active items found. Please run bootstrap first.")
    finally:
        session.close()
