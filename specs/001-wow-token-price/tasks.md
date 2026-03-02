---
description: "Task list for wow-token-price implementation"
---

# Tasks: wow-token-price

**Input**: Design documents from `/specs/001-wow-token-price/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Organization**: Tasks are grouped by initialization, foundation (Docker/DB), and user story execution (Background Worker).

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialização do novo projeto Python no backend e gestão de dependências isoladas.

- [x] T001 Initialize Python toolchain (`uv` / `pip`) at `backend/` and configure Python 3.11+.
- [x] T002 Add primary dependencies (`requests`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `python-dotenv`) in `backend/requirements.txt` or `pyproject.toml`.
- [x] T003 Add testing dependencies (`pytest`, `pytest-mock`) for Phase 3.
- [x] T004 [P] Create `.env.example` at `backend/` using keys from `quickstart.md`.

---

## Phase 2: Foundational (Docker & Database)

**Purpose**: Estrutura obrigatória de contêiner e persistência de dados (PostgreSQL) ditada pelos princípios de isolamento.
**⚠️ CRITICAL**: A estrutura deve estar pronta antes que o Worker ganhe vida.

- [x] T005 Create `backend/docker-compose.yml` configuring the `postgres:16-alpine` service.
- [x] T006 Add `Dockerfile` at `backend/` to containerize the Python worker.
- [x] T007 Configure `backend/docker-compose.yml` to include the `worker` service linking it to the database.
- [x] T008 [P] Implement base SQLAlchemy Entity setup and Engine connection in `backend/src/repositories/database.py`.
- [x] T009 Implement the `ITEM_PRICE` table model in `backend/src/models/item_price.py` per `data-model.md`.
- [x] T010 Create DB migration/initialization script inside `backend/src/repositories/database.py` to create tables on boot.

**Checkpoint**: Banco de dados pode subir via `docker-compose up db` e tabelas existem com sucesso.

---

## Phase 3: User Story 1 - Obter Preço Atual da Ficha de WoW (Priority: P1) 🎯 MVP

**Goal**: Rastrear o preço atualizado do WoW Token (ID: 122284) buscando os dados oficiais e guardando no banco.
**Independent Test**: Executar `worker.py` manualmente extrai, loga e insere os dados no DB pelo menos 1 vez com sucesso.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US1] Unit test for Blizzard OAuth logic in `backend/tests/unit/test_auth.py`.
- [x] T012 [P] [US1] Unit test for WoW Token parsing logic in `backend/tests/unit/test_api_client.py`.
- [x] T013 [P] [US1] Integration test covering insertion to DB with mocked API response in `backend/tests/integration/test_worker_insert.py`.

### Implementation for User Story 1

- [x] T014 [P] [US1] Create models `OAuthToken` and `WoWTokenResponse` in `backend/src/models/api_models.py` using Pydantic per `api.md`.
- [x] T015 [US1] Implement `AuthTokenManager` in `backend/src/services/auth.py` (Client Credentials Grant).
- [x] T016 [US1] Implement `BlizzardApiClient` in `backend/src/services/api_client.py` for `/data/wow/token/index`.
- [x] T017 [US1] Create `ItemPriceRepository` in `backend/src/repositories/item_price_repository.py` to handle database inserts.
- [x] T018 [US1] Implement `backend/src/worker.py` loop scheduler tying Auth, Client, and Repository together.

**Checkpoint**: `docker-compose up` sobe o Worker com sucesso, requisita a Blizzard e o registro aparece no terminal/banco de dados.

---

## Phase 4: Polish & Extensibility

**Purpose**: Refinamentos cruzados de robustez requisitados na especificação.

- [x] T019 Update `backend/src/worker.py` and Services to gracefully handle API downtime (Edge Case 1).
- [x] T020 Update `backend/src/services/auth.py` to auto-renew/pausar execution if Token expires (Edge Case 2).
- [x] T021 [P] Extract hardcoded "122284" tracking into an environment variable or list to support future items parsing.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup to have Python configured.
- **User Story 1 (Phase 3)**: Depends completely on Phase 2 (DB online + Models).
- **Polish (Phase 4)**: Executes post-MVP verifications.

### Implementation Strategy

1. Complete Setup + Foundational (Configure Docker and instantiate PG).
2. Generate all tests for US1.
3. Build logic and run tests iteratively (Red-Green-Refactor).
4. Run `docker-compose logs worker` to validate end-to-end extraction.
5. Apply edge case resilience blocks.
