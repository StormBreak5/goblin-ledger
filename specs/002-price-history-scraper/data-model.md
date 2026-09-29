# Data Model: Price History Scraper

## Entities

### 1. HistoricalItemPrice

Represents a single historical price point for an item.

**Fields**:
- `id` (UUID, Primary Key)
- `item_id` (Integer, Indexed)
- `region` (String, Indexed)
- `timestamp` (DateTime, Indexed)
- `price` (BigInteger) - Stored in copper or lowest currency unit
- `quantity` (Integer, Optional) - Available quantity at that time, if provided

**Database Constraints**:
- `UNIQUE(item_id, region, timestamp)`: Prevents duplicate historical records if the backfill script is run multiple times.

### 2. ScraperExecutionLog

Represents an audit log of backfill executions.

**Fields**:
- `id` (UUID, Primary Key)
- `execution_start` (DateTime)
- `execution_end` (DateTime, Nullable)
- `status` (Enum: `RUNNING`, `SUCCESS`, `FAILED`)
- `items_processed` (Integer)
- `records_inserted` (Integer)
- `error_message` (Text, Nullable)

## State Transitions
- **Scraper Execution**: `RUNNING` -> `SUCCESS` (if finishes all items) or `FAILED` (if unhandled exception occurs).
