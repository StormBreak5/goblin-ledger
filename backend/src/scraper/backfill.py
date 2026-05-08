import argparse
import sys
import logging
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.scraper.models import HistoricalItemPrice, ScraperExecutionLog, ExecutionStatus
from src.scraper.undermine_client import UndermineClient

logger = logging.getLogger(__name__)

def get_items_to_process(session: Session) -> List[int]:
    """
    Retrieves the list of active tracked item IDs from the database.
    """
    from src.models.tracked_item import TrackedItem
    items = session.query(TrackedItem.external_item_id).filter(
        TrackedItem.game == 'wow',
        TrackedItem.is_active == True
    ).all()
    return [int(it[0]) for it in items]

def run_backfill(session: Session, item_ids: List[int], region: str):
    """Run the backfill process for a list of items."""
    
    log = ScraperExecutionLog(
        execution_start=datetime.utcnow(),
        status=ExecutionStatus.RUNNING,
        items_processed=0,
        records_inserted=0
    )
    session.add(log)
    session.commit()
    
    client = UndermineClient()
    
    total_inserted = 0
    
    try:
        for item_id in item_ids:
            prices = client.fetch_item_history(item_id, region)
            
            if not prices:
                continue
                
            # Prepare data for upsert
            values = []
            for p in prices:
                values.append({
                    "item_id": p.item_id,
                    "region": p.region,
                    "timestamp": p.timestamp,
                    "price": p.price,
                    "quantity": p.quantity
                })
                
            # PostgreSQL specific upsert
            stmt = insert(HistoricalItemPrice).values(values)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['item_id', 'region', 'timestamp']
            )
            
            result = session.execute(stmt)
            inserted_count = result.rowcount
            total_inserted += inserted_count
            
            log.items_processed += 1
            session.commit()
            
            logger.info(f"Processed item {item_id}. Inserted {inserted_count} new records.")

        log.status = ExecutionStatus.SUCCESS
        log.records_inserted = total_inserted
        log.execution_end = datetime.utcnow()
        session.commit()
        
    except KeyboardInterrupt:
        logger.warning("Backfill interrupted by user.")
        log.status = ExecutionStatus.FAILED
        log.error_message = "KeyboardInterrupt"
        log.execution_end = datetime.utcnow()
        session.commit()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        log.status = ExecutionStatus.FAILED
        log.error_message = str(e)
        log.execution_end = datetime.utcnow()
        session.commit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Run historical price backfill.")
    parser.add_argument("--region", type=str, default="US", help="Region to backfill")
    args = parser.parse_args()
    
    from src.repositories.database import init_db, get_session
    from dotenv import load_dotenv
    
    load_dotenv()
    init_db()
    
    session = get_session()
    item_ids = get_items_to_process(session)
    
    logger.info(f"Starting backfill for {len(item_ids)} items in region {args.region}")
    
    try:
        run_backfill(session, item_ids, args.region)
        logger.info("Backfill completed successfully.")
    finally:
        session.close()
