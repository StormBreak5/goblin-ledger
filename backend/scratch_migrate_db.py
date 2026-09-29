import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.repositories.database import init_db, get_session

def run_migration():
    session = get_session()
    try:
        session.execute(text("DROP TABLE IF EXISTS tracked_items CASCADE;"))
        session.execute(text("DROP INDEX IF EXISTS idx_game_external_id CASCADE;"))
        session.commit()
        print("Dropped table tracked_items successfully.")
    except Exception as e:
        print(f"Error dropping table: {e}")
        session.rollback()
    finally:
        session.close()
        
    init_db()
    print("Database initialized (new items table should be created).")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_migration()
