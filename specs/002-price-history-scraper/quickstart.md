# Quickstart: Price History Scraper Backfill

This script allows you to backfill the database with historical item prices from Undermine Exchange.

## Prerequisites
- Docker containers running (`docker-compose up -d`)
- Python 3.11+ configured locally or via the worker container.

## How to Run

You can execute the backfill script directly inside the worker container or locally.

### Executing via Docker (Recommended)

```bash
docker-compose exec worker python -m src.scraper.backfill
```

### Executing Locally

1. Set up the virtual environment:
```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

2. Run the script:
```bash
python -m src.scraper.backfill
```

## Monitoring
The script will log its progress to `stdout`. It implements a delay between requests to avoid IP bans. If interrupted, it can be safely restarted, as the database relies on `ON CONFLICT DO NOTHING` to prevent duplicates.
