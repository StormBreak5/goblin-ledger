---
description: "Task list for Price History Scraper implementation"
---

# Tasks: Price History Scraper

**Input**: Design documents from `/specs/002-price-history-scraper/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, quickstart.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for the scraper module

- [x] T001 Create `__init__.py` files to initialize `backend/src/scraper/` and `backend/tests/scraper/` packages
- [x] T002 Add or verify `pydantic`, `pytest`, and `pytest-mock` dependencies in backend requirements

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create SQLAlchemy models for `HistoricalItemPrice` and `ScraperExecutionLog` with unique constraints in `backend/src/scraper/models.py`
- [x] T004 Create Pydantic validation schemas for the Undermine Exchange JSON payload in `backend/src/scraper/models.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Collect Historical Price Data (Priority: P1) 🎯 MVP

**Goal**: Fetch historical price data for tracked items from Undermine Exchange internal JSON files safely and reliably.

**Independent Test**: Can be fully tested by triggering the data collection process for a single specific item and verifying that the system successfully receives and parses the historical data payload in memory.

### Tests for User Story 1 ⚠️

- [x] T005 [P] [US1] Create unit tests for Undermine client HTTP and retry logic in `backend/tests/scraper/test_undermine_client.py`

### Implementation for User Story 1

- [x] T006 [US1] Implement `UndermineClient` class with requests, exponential backoff, and rate limiting in `backend/src/scraper/undermine_client.py`
- [x] T007 [US1] Integrate Pydantic schemas to validate and parse the JSON responses within the client

**Checkpoint**: At this point, User Story 1 should be fully functional (able to fetch and parse JSON into memory).

---

## Phase 4: User Story 2 - Persist Historical Data (Priority: P1)

**Goal**: Save all collected records into the PostgreSQL database without duplicating existing records.

**Independent Test**: Can be fully tested by feeding a mock JSON payload of historical prices to the storage component and verifying the database state handles duplicates correctly.

### Tests for User Story 2 ⚠️

- [x] T008 [P] [US2] Create unit and integration tests for duplicate prevention (upsert) in `backend/tests/scraper/test_backfill.py`

### Implementation for User Story 2

- [x] T009 [US2] Implement database `UPSERT` logic (ON CONFLICT DO NOTHING) using SQLAlchemy for `HistoricalItemPrice` in `backend/src/scraper/backfill.py`
- [x] T010 [US2] Implement the main CLI entry point orchestrating the client and storage logic in `backend/src/scraper/backfill.py`
- [x] T011 [US2] Add execution logging to insert a `ScraperExecutionLog` record at the start and end of the backfill process

**Checkpoint**: At this point, the scraper can fetch, validate, and safely save data without duplicates.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T012 Run linters (`ruff`/`flake8`) and type checkers (`mypy`) on `backend/src/scraper/` to enforce Type Safety
- [x] T013 Verify the CLI command handles KeyboardInterrupt (Ctrl+C) gracefully to fail the `ScraperExecutionLog` cleanly
- [x] T014 Update the main `README.md` to reference the scraper backfill capabilities

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 must be completed before US2, as US2 relies on the fetched data structure to persist it.
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### Parallel Opportunities

- Tests marked `[P]` (T005, T008) can be written in parallel with Foundational tasks or before their respective implementation tasks.

## Implementation Strategy

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (Models created)
2. Add User Story 1 → Test independently → Able to fetch and parse external JSON
3. Add User Story 2 → Test independently → Able to save fetched JSON reliably to DB
4. Run polish phase to verify types and error handling
