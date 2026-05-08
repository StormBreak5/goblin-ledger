import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.scraper.models import Base, HistoricalItemPrice, ExecutionStatus, ScraperExecutionLog
from src.scraper.backfill import run_backfill

# For simplicity in testing, we use an in-memory SQLite database.
# Note: SQLite supports INSERT OR IGNORE, which is slightly different from Postgres ON CONFLICT DO NOTHING.
# Since SQLAlchemy handles dialects, we'll test the logic mostly with mocks or basic DB.
# For a true Postgres upsert test, we would need a test postgres container.
# Here we will mock the insert behavior.

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_backfill_execution_log(db_session, mocker):
    mocker.patch("src.scraper.backfill.UndermineClient")
    
    # Run backfill for no items
    run_backfill(db_session, item_ids=[], region="US")
    
    logs = db_session.query(ScraperExecutionLog).all()
    assert len(logs) == 1
    assert logs[0].status == ExecutionStatus.SUCCESS
    assert logs[0].items_processed == 0
    assert logs[0].records_inserted == 0
    assert logs[0].execution_end is not None

def test_backfill_with_items(db_session, mocker):
    mock_client_instance = MagicMock()
    # Return 2 valid prices for the item
    mock_client_instance.fetch_item_history.return_value = [
        MagicMock(item_id=1, region="US", timestamp=datetime(2026, 1, 1), price=100, quantity=None),
        MagicMock(item_id=1, region="US", timestamp=datetime(2026, 1, 2), price=200, quantity=None)
    ]
    mocker.patch("scraper.backfill.UndermineClient", return_value=mock_client_instance)
    
    # We will mock the Postgres upsert since SQLite doesn't natively support Postgres's ON CONFLICT dialect easily in same code
    mock_insert = mocker.patch("scraper.backfill.insert")
    mock_execute = mocker.patch.object(db_session, "execute")
    
    run_backfill(db_session, item_ids=[1], region="US")
    
    assert mock_client_instance.fetch_item_history.called
    assert mock_execute.called
    
    # Check log
    logs = db_session.query(ScraperExecutionLog).all()
    assert len(logs) == 1
    assert logs[0].status == ExecutionStatus.SUCCESS
    assert logs[0].items_processed == 1

def test_backfill_failure(db_session, mocker):
    mock_client_instance = MagicMock()
    mock_client_instance.fetch_item_history.side_effect = Exception("API Down")
    mocker.patch("scraper.backfill.UndermineClient", return_value=mock_client_instance)
    
    # We do not want the whole script to crash if one item fails, unless it's a fatal error.
    # If the script is designed to catch it:
    run_backfill(db_session, item_ids=[1], region="US")
    
    logs = db_session.query(ScraperExecutionLog).all()
    assert len(logs) == 1
    assert logs[0].status == ExecutionStatus.FAILED
    assert "API Down" in logs[0].error_message
