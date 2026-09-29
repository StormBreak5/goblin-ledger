import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, RequestException
from src.scraper.undermine_client import UndermineClient
from src.scraper.models import UndermineItemPrice
from datetime import datetime

@pytest.fixture
def mock_client():
    return UndermineClient(base_url="http://test.com", delay=0)

def test_fetch_item_history_success(mock_client, mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"item_id": 123, "region": "US", "timestamp": "2026-05-01T12:00:00Z", "price": 1000, "quantity": 10}
        ]
    }
    mocker.patch("requests.Session.get", return_value=mock_response)

    results = mock_client.fetch_item_history(123, "US")
    assert len(results) == 1
    assert isinstance(results[0], UndermineItemPrice)
    assert results[0].price == 1000

def test_fetch_item_history_timeout_retry(mock_client, mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}
    
    # Fail first time, succeed second
    mocker.patch("requests.Session.get", side_effect=[Timeout("Timeout"), mock_response])
    
    results = mock_client.fetch_item_history(123, "US")
    assert results == []

def test_fetch_item_history_max_retries_exceeded(mock_client, mocker):
    mocker.patch("requests.Session.get", side_effect=Timeout("Timeout"))
    
    with pytest.raises(RequestException):
        mock_client.fetch_item_history(123, "US")

def test_fetch_item_history_rate_limiting(mock_client, mocker):
    mock_client.delay = 0.1 # 100ms
    mocker.patch("requests.Session.get", return_value=MagicMock(status_code=200, json=lambda: {"data": []}))
    
    import time
    start = time.time()
    mock_client.fetch_item_history(123, "US")
    mock_client.fetch_item_history(124, "US")
    end = time.time()
    
    assert end - start >= 0.1
