import time
import logging
import requests
from typing import List
from requests.exceptions import RequestException

from src.scraper.models import UndermineItemPrice

logger = logging.getLogger(__name__)

class UndermineClient:
    """Client for fetching historical data from Undermine Exchange."""
    
    def __init__(self, base_url: str = "https://undermine.exchange/api", delay: float = 1.0, max_retries: int = 3):
        self.base_url = base_url
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GoblinLedger/1.0 (Historical Backfill)"
        })
        self._last_request_time = 0.0

    def _wait_for_rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def fetch_item_history(self, item_id: int, region: str) -> List[UndermineItemPrice]:
        """Fetch and parse historical item prices."""
        # Note: the exact URL structure depends on Undermine Exchange's internal API.
        # Assuming a structure like /history/{region}/{item_id}
        url = f"{self.base_url}/history/{region}/{item_id}"
        
        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json().get("data", [])
                
                # Parse with Pydantic
                parsed_prices = []
                for item in data:
                    try:
                        parsed_prices.append(UndermineItemPrice.model_validate(item))
                    except ValueError as e:
                        logger.warning(f"Failed to parse historical data point: {e}")
                
                return parsed_prices
                
            except RequestException as e:
                logger.error(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt) # Exponential backoff
        
        return []
