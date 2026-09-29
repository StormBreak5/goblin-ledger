# Feature Specification: Price History Scraper

**Feature Branch**: `002-price-history-scraper`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "agora quero construir a parte do scrapper, preciso que você me pergunte toda duvida que tiver, mas no momento penso em coletar todo o histórico de preço dos itens, que pode ser pego por json (eu acho) no undermine exchange ou algum método semelhante para coleta, assim que coletado, quero salvar no banco de dados"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Collect Historical Price Data (Priority: P1)

The system needs to fetch the entire historical price data for tracked items from an external data source (such as Undermine Exchange) so that the application has a comprehensive dataset for predictive market analysis.

**Why this priority**: Without historical data, the predictive analysis goals of the project cannot be achieved. This is the foundational step for data acquisition.

**Independent Test**: Can be fully tested by triggering the data collection process for a single specific item and verifying that the system successfully receives and parses the historical data payload in memory.

**Acceptance Scenarios**:

1. **Given** a valid item identifier, **When** the scraper requests data from the external API, **Then** the system receives and successfully parses the historical price JSON payload.
2. **Given** an external API timeout or unavailability, **When** the scraper attempts to fetch data, **Then** the system logs the error gracefully and aborts the operation without crashing.

---

### User Story 2 - Persist Historical Data (Priority: P1)

Once the historical data is collected, the system must save all the records into the database. It must ensure that existing records are not duplicated if the process is executed multiple times.

**Why this priority**: Collecting data is useless if it's not permanently stored for later analysis. Ensuring data integrity (no duplicates) is critical for accurate predictive models.

**Independent Test**: Can be fully tested by feeding a mock JSON payload of historical prices to the storage component and verifying the database state.

**Acceptance Scenarios**:

1. **Given** a parsed list of historical prices, **When** the storage process executes, **Then** all new price records are successfully saved to the database.
2. **Given** a list of prices that already exist in the database, **When** the storage process executes, **Then** the system ignores the duplicates and only inserts new or missing records.

---

### Edge Cases

- What happens when the external API returns an unexpectedly large payload (e.g., millions of records)?
- How does the system handle temporary IP bans or rate limiting from the external source?
- What happens if the data structure returned by the API changes unexpectedly?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST be able to request historical price data for specific items from an external JSON API.
- **FR-002**: System MUST parse the received JSON data into a structured format compatible with the application's domain.
- **FR-003**: System MUST save the historical price data into the primary database.
- **FR-004**: System MUST NOT duplicate existing price records if the scraper is run multiple times for the same time period.
- **FR-005**: System MUST handle API connection errors and timeouts gracefully, logging the failure without crashing.
- **FR-006**: System MUST extract historical data from Undermine Exchange's internal JSON files (since the official Blizzard API lacks historical endpoints) and implement respectful delays between requests to prevent IP bans.
- **FR-007**: System MUST attempt to collect the price history for ALL possible items available in the Auction House.
- **FR-008**: System MUST be designed as a one-time historical backfill script (manual execution) to seed the database for model training, leaving ongoing real-time data collection to the existing worker.

### Key Entities

- **Item Price History**: Represents a single historical price point. Key attributes include Item ID, Timestamp/Date, Price value, and Region/Realm identifier.
- **Scraper Execution Log**: Represents a record of a scraping attempt, including start time, end time, items processed, success/failure status, and rows inserted.

### Assumptions & Dependencies

- **External Source Limits**: Undermine Exchange has no public API and relies on static internal JSON files. The scraper assumes these files remain accessible and their structure is relatively stable.
- **Division of Responsibility**: This historical scraper is strictly for backfilling data for model training. The main application worker (using the official Blizzard API) remains responsible for current, ongoing price collection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System successfully retrieves and stores the full available history for a specified item without memory exhaustion.
- **SC-002**: Database contains 0 duplicate price entries for the same item at the exact same timestamp after multiple scraper runs.
- **SC-003**: In the event of a network failure, the system completes error handling and logging within 10 seconds.
- **SC-004**: The data collection process can successfully parse and map 100% of the historical price data points provided in a valid API response.
