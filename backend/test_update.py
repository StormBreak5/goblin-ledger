import logging
logging.basicConfig(level=logging.INFO)
from dotenv import load_dotenv
load_dotenv()
from src.repositories.database import get_session
from src.models.item import Item
from sqlalchemy import update

session = get_session()
item = session.query(Item).filter_by(external_item_id='10001').first()
print(f"Before: {item.name}")

results = [{"id": item.id, "name": "Test Update Name", "icon_url": "http://test.com"}]
session.execute(update(Item), results)
session.commit()

item2 = session.query(Item).filter_by(external_item_id='10001').first()
print(f"After: {item2.name}, {item2.icon_url}")
