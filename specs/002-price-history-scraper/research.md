# Research: Price History Scraper

## Technical Context Unknowns
No major unknowns were identified during planning that required external research. The technical stack is well defined by the constitution (Python, SQLAlchemy, PostgreSQL, pytest). 

## Technology Choices

### 1. Data Validation
- **Decision**: Use `Pydantic`.
- **Rationale**: The Constitution (Principle I) requires explicit type hints and a validation library for API boundaries. Pydantic is the standard and most robust choice for parsing and validating JSON in modern Python.
- **Alternatives considered**: Standard `json` parsing with manual `dict` validation (rejected as it violates Principle I) or `marshmallow` (Pydantic is more idiomatic with Python 3.11+ type hints).

### 2. Rate Limiting Strategy
- **Decision**: Implement a token bucket or simple `time.sleep` with exponential backoff.
- **Rationale**: Undermine Exchange has no official public API and discourages scraping. Implementing a respectful delay (e.g., 1-2 seconds between requests) ensures we do not overload their servers or trigger IP bans.
- **Alternatives considered**: Async fetching with `aiohttp` to maximize speed (rejected because it would likely trigger rate limits/bans immediately).

### 3. Duplicate Prevention
- **Decision**: PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` (Upsert).
- **Rationale**: Relying on database-level constraints ensures race conditions or multiple runs don't create duplicates. We will define a unique constraint on `(item_id, timestamp, region)`.
- **Alternatives considered**: Querying first and only inserting missing records (rejected due to inefficiency with large datasets).
