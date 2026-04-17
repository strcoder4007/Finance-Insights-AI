# Finance Insights AI — Handoff Document

## 1. Overview

RESTful NL-to-SQL engine for financial data. Ingest two P&L JSON sources (QuickBooks-style + Rootfi-style) into a canonical monthly SQLite schema, expose endpoints for metrics/periods/breakdown/chat, and answer natural language finance queries without hallucinating numbers.

Guiding rule: **numbers come from SQLite**. The LLM handles planning and narration; backend executes all SQL deterministically.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.x |
| Database | SQLite (plain `sqlite3`, no ORM) |
| AI | OpenAI API (GPT-5-mini for planner, GPT-5 for narrator) |
| Frontend | Vue 3 (separate) |
| Ingestion | Custom adapters for QuickBooks and Rootfi JSON formats |

---

## 3. Project Structure

```
Finance-Insights-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI factory + lifespan (init_db, configure_logging)
│   │   ├── api/v1/
│   │   │   ├── chat.py             # POST /chat endpoint
│   │   │   ├── ingest.py           # POST /ingest endpoint
│   │   │   ├── metrics.py          # GET /metrics/timeseries, GET /metrics/compare
│   │   │   └── periods.py          # GET /periods, GET /breakdown
│   │   ├── services/
│   │   │   ├── nlq_service.py      # Planner → validator → executor → narrator loop
│   │   │   ├── ingest_service.py    # Two-phase ingestion (raw → canonical)
│   │   │   ├── query_service.py     # metric_timeseries, breakdown, compare_periods
│   │   │   └── types.py             # Pydantic models for NLQ plan calls
│   │   ├── adapters/
│   │   │   ├── quickbooks_pnl.py    # Parse QuickBooks-style JSON (hierarchical rows)
│   │   │   └── rootfi_pnl.py        # Parse Rootfi-style monthly P&L
│   │   ├── core/
│   │   │   ├── settings.py          # Env vars: DB_PATH, DATA1/2_PATH, OPENAI_API_KEY, etc.
│   │   │   └── logging.py           # Structured logging setup
│   │   └── db/
│   │       ├── schema.sql           # Full SQLite schema (period, raw_metric, raw_line_item, metric_value, line_item_value, chat_session, chat_message, ingestion_run, ingestion_issue)
│   │       ├── repo.py              # All parameterized SQL queries (no ORM)
│   │       └── sqlite.py            # DB connection management
│   ├── .env.example
│   ├── requirements.txt
│   └── app.db                       # SQLite DB (gitignored, generated on first ingest)
├── frontend/                        # Vue 3 app
├── data1.json                       # QuickBooks P&L (bundled sample data)
├── data2.json                       # Rootfi P&L (bundled sample data)
├── render.yaml                      # Render deployment blueprint
├── IMPLEMENTATION.md                # Deep dive: merge rules, canonical model, NLQ architecture
└── README.md
```

### Key Files

- **backend/app/services/nlq_service.py** — `NLQService.chat()`. Two-step guarded NLQ: (1) Planner emits JSON plan (ListPeriodsCall / QueryMetricCall / QueryBreakdownCall / ComparePeriodsCall), validated by Pydantic with allowlists + range checks. (2) Backend executes calls deterministically via `QueryService`, sends results to Narrator LLM for natural language answer. Falls back to clarifying question on parse failures.

- **backend/app/services/ingest_service.py** — Two-phase ingestion: raw observation storage then canonical merge. Handles QuickBooks (hierarchical Rows tree with section summaries) and Rootfi (already month-granular with scalar metrics + category trees). Reconciles conflicts via `MERGE_TOLERANCE` (absolute or percent). Logs issues to `ingestion_issue` table.

- **backend/app/adapters/quickbooks_pnl.py** — Parser for QuickBooks-style JSON: section-summary rows (`Net Income`, `Gross Profit`) map to canonical metrics; leaf row tree (Income/COGS/Expenses) map to line items.

- **backend/app/adapters/rootfi_pnl.py** — Parser for Rootfi-style JSON: already monthly with `period_start`/`period_end`, scalar metrics + category trees, includes `account_id`.

- **backend/app/db/repo.py** — All raw SQL. Key functions: `upsert_period`, `upsert_raw_metric`, `upsert_raw_line_item`, `upsert_metric_value`, `upsert_line_item_value`, `fetch_metric_monthly`, `fetch_line_items`, `list_periods_with_sources`.

- **backend/app/db/schema.sql** — Complete schema:
  - `period`: `(id, period_start, period_end, currency)` — unique constraint on (period_start, period_end)
  - `raw_metric_value`: `(period_id, source, metric, value)` — per-source observations
  - `raw_line_item_value`: `(period_id, source, category, path, name, account_id, value)` — per-source line items
  - `metric_value`: canonical merged metrics
  - `line_item_value`: canonical merged line items
  - `chat_session`, `chat_message`: conversation persistence
  - `ingestion_run`, `ingestion_issue`: reconciliation metadata

- **backend/app/services/query_service.py** — `QueryService` class with `metric_timeseries()`, `breakdown()`, `compare_periods()`. All use parameterized SQL against canonical tables.

---

## 4. How It Works

### Ingestion Flow

1. `POST /api/v1/ingest` with `{mode: "replace"|"append"}` calls `IngestService.run()`
2. Phase 1 — Raw Storage:
   - `quickbooks_pnl.py` extracts section-summary metrics (Net Income → `net_income`) and leaf line items (path hierarchy, e.g. `Business Expenses > Rent`)
   - `rootfi_pnl.py` extracts monthly scalar metrics and category trees with `account_id`
   - All stored in `raw_metric_value` and `raw_line_item_value` per source
3. Phase 2 — Canonical Merge:
   - For each `(period, metric)`: if both sources present and within tolerance → use primary source, provenance = `primary+other`; if conflict → use primary + log `ingestion_issue`
   - For line items: intentionally avoid cross-source mapping to prevent double-counting; pick primary source's leaf set per `(period, category)`
   - Results stored in `metric_value` and `line_item_value`
4. Reconciliation: any discrepancies logged to `ingestion_issue` table for transparency

### NLQ Chat Flow

1. `POST /api/v1/chat` with `{message, session_id?}` → `NLQService.chat()`
2. Session created/persisted via `repo.ensure_chat_session` + `repo.insert_chat_message`
3. `_generate_plan()`: Planner LLM (GPT-5-mini, temperature=0) receives system prompt + chat history; outputs JSON plan with calls from allowlisted types only
4. JSON validated by `NLQPlan` Pydantic model (extra="forbid", discriminator on "name", max 5 calls)
5. On validation failure: retry once with error feedback; fallback to clarifying question if still fails
6. Plan executed in order:
   - `ListPeriodsCall` → `repo.list_periods()`
   - `QueryMetricCall` → `QueryService.metric_timeseries()`
   - `QueryBreakdownCall` → `QueryService.breakdown()`
   - `ComparePeriodsCall` → `QueryService.compare_periods()`
7. Each call result → `_result_summary()` (compact representation for logging)
8. `_narrate_answer()`: Narrator LLM receives user question + plan + tool outputs → natural language answer using only provided facts
9. Answer + supporting_data + tool_calls_log persisted and returned

---

## 5. Current State

**Working:**
- Full ingestion pipeline (QuickBooks + Rootfi → canonical SQLite)
- All REST endpoints: `/periods`, `/metrics/timeseries`, `/metrics/compare`, `/breakdown`, `/ingest`, `/chat`
- Two-step guarded NLQ with Pydantic validation, allowlists, max-call cap
- Chat history persistence across sessions
- Structured logging with request correlation

**Known gaps / rough edges:**
- No user authentication / multi-tenant isolation on chat sessions
- No API key authentication on REST endpoints (assumes internal network)
- `IMPLEMENTATION.md` is comprehensive but not updated with latest changes
- No automated tests in the repo
- `render.yaml` is a starting point but not validated against actual deployment
- No rate limiting or cost controls on OpenAI calls
- `MERGE_TOLERANCE` logic is binary (within tolerance vs outside); no median/mean reconciliation strategy

---

## 6. Improvements

### 1. API Authentication & Rate Limiting
**What to do:** Add `fastapi-auth` or `fastapi-users` with API key validation. Add `slowapi` rate limiting (e.g., 60 req/min per API key). Protect all `/api/v1/` endpoints. Add `X-API-Key` header validation middleware.

**Why it matters:** Exposing financial data over unauthenticated endpoints is a critical security risk. Staff Engineers building enterprise SaaS must have auth from day one.

**Files likely to touch:** `backend/app/main.py` (middleware), new `backend/app/api/v1/auth.py`, `backend/app/core/settings.py` (add auth config)

**Verification:** Call `/api/v1/periods` without API key → 401; with valid key → 200. Send 100 req/min → 429.

---

### 2. Automated Test Suite
**What to do:** Add `pytest`, `pytest-asyncio`, `httpx` for FastAPI testing. Write tests: `test_ingest_replace_clears_old_data`, `test_ingest_quickbooks_parses_metric_totals`, `test_nlq_planner_validates_schema`, `test_nlq_falls_back_to_clarify_on_bad_json`, `test_query_metric_timeseries_returns_series`, `test_chat_persists_message_history`. Use in-memory SQLite for test DB.

**Why it matters:** Without tests, any refactor risks silently breaking the ingestion pipeline, NLQ validation, or chat persistence. Finance data correctness is non-negotiable.

**Files likely to touch:** `backend/tests/` (new), `backend/requirements.txt` (add pytest deps), `backend/app/services/nlq_service.py` (make chat testable via dependency injection)

**Verification:** `pytest tests/` passes with >80% coverage on core modules.

---

### 3. Cross-Source Line Item Fuzzy Matching
**What to do:** Implement optional fuzzy matching for line items across sources. Compute Jaccard similarity on path tokens. If similarity > threshold (e.g., 0.7) and both sources have values within tolerance → reconcile rather than pick-primary. Store provenance = `reconciled`. Requires updating `repo.py` and `ingest_service.py`.

**Why it matters:** Currently line items are never reconciled across sources (intentional to avoid double-counting). But for categories where both sources use the same taxonomy, users lose the benefit of dual sourcing. Staff Engineers building reconciliation tools need this.

**Files likely to touch:** `backend/app/services/ingest_service.py` (reconciliation loop), `backend/app/db/repo.py` (upsert with similarity), new `backend/app/core/matching.py`

**Verification:** Ingest data where data1.json and data2.json both have "Rent" in operating_expense; verify it's reconciled and provenance = "reconciled".

---

### 4. Better Merge Tolerance Diagnostics
**What to do:** Add a `GET /api/v1/ingestion/issues` endpoint that returns all `ingestion_issue` records with run_id, level, message, period, metric, source, details. Add a dashboard-level summary: count of conflicts, percentage of metrics with dual provenance, tolerance breach list.

**Why it matters:** Currently, tolerance breaches are logged to the DB but there's no API to retrieve them. Users have no visibility into data quality issues. Staff Engineers building data quality tools need observability.

**Files likely to touch:** `backend/app/api/v1/ingest.py` (new endpoint), `backend/app/db/repo.py` (fetch_ingestion_issues query)

**Verification:** Trigger an ingestion with intentional data mismatch; call `/api/v1/ingestion/issues`; observe returned conflict records.

---

### 5. Chat Session Export
**What to do:** Add `GET /api/v1/chat/{session_id}/export` that returns full conversation as JSON (messages with role, content, timestamps). Optionally support CSV export for analysis in Excel.

**Why it matters:** Finance teams need to archive conversations for audit trails. Currently there's no export mechanism — the chat history is only accessible via the chat API itself.

**Files likely to touch:** `backend/app/api/v1/chat.py` (new endpoint), `backend/app/db/repo.py` (already has `fetch_chat_messages`)

**Verification:** Create a chat session with 5 messages; call export endpoint; confirm all 5 messages present with correct role/content ordering.

---

### 6. Temperature Model Routing Fix
**What to do:** The `_model_supports_temperature()` function returns `False` for `gpt-5` models. GPT-5 does support temperature. Fix the condition to check for actual model capability rather than prefix-matching "gpt-5". Add integration test that confirms temperature is passed correctly for both GPT-4 and GPT-5 models.

**Why it matters:** Currently GPT-5 models run at default temperature (likely >0.2), causing potentially less consistent narration. The `temperature=0.2` on narrator is intentional for natural but controlled output.

**Files likely to touch:** `backend/app/services/nlq_service.py` (`_model_supports_temperature` function), add `tests/test_nlq_service.py`

**Verification:** Mock OpenAI client, send same message with gpt-5 model, verify temperature=0.2 in API call.

---

### 7. Frontend Chart.js Upgrade Path
**What to do:** The frontend uses Chart.js for time series visualization. Verify chart handles missing data points gracefully (gaps in time series). Add interactive tooltip with period + value. Consider upgrading to Chart.js 4.x if not already on it, since it has better TypeScript support and performance improvements.

**Why it matters:** Chart.js is the only data visualization library; it needs to handle real financial data edge cases (missing months, negative values, large ranges). Staff Engineers care about the quality of the analytics UI as much as the backend.

**Files likely to touch:** `frontend/src/components/Chart.vue` (if exists), `frontend/package.json` (Chart.js version pin)

**Verification:** Load a time series with a missing month; chart renders with gap, not interpolated.

---

### 8. PostgreSQL Migration Path
**What to do:** The current architecture uses SQLite for simplicity. Prepare a migration path to PostgreSQL for production: replace `sqlite3` connections with `asyncpg`, update `repo.py` to use async SQL, update `schema.sql` for PostgreSQL syntax (e.g., `SERIAL` → `BIGSERIAL`, `GROUP_CONCAT` → `string_agg`). Add a `DB_TYPE` env var to switch between sqlite and postgres.

**Why it matters:** SQLite doesn't support concurrent writes and has file-size limits. Production finance systems need PostgreSQL. Staff Engineers building multi-tenant SaaS need a clear migration path rather than a rewrite.

**Files likely to touch:** `backend/app/db/sqlite.py` (abstract to `backend/app/db/connection.py`), `backend/app/db/repo.py` (async variants), `backend/app/core/settings.py` (DB_TYPE config), `backend/requirements.txt` (add asyncpg)

**Verification:** Set `DB_TYPE=postgres`, point at a live Postgres instance, run ingest, query periods → correct results.

---

### 9. Configurable Chat History Limit
**What to do:** Currently `chat_history_limit` is in `settings.py` but hardcoded. Expose it as an env var `CHAT_HISTORY_LIMIT` with a sane default (20). Pass it to `NLQService` constructor and use it in `_generate_plan()` to limit context window.

**Why it matters:** Long chat sessions with many turns consume excessive tokens. Finance analysts may run very long sessions when doing deep analysis. A configurable limit lets operators tune cost vs. context richness.

**Files likely to touch:** `backend/app/core/settings.py` (add `CHAT_HISTORY_LIMIT` env var), `backend/app/services/nlq_service.py` (use `self.settings.chat_history_limit`)

**Verification:** Set `CHAT_HISTORY_LIMIT=2`, send 5 messages, confirm planner only sees last 2 in history.

---

### 10. Ingestion Progress Tracking
**What to do:** The `POST /ingest` endpoint currently blocks until completion (can be slow with large JSON files). Add async ingestion with progress tracking: start background task, return `{run_id, status: "started"}`. Add `GET /api/v1/ingest/{run_id}/status` endpoint that returns current phase (parsing/raw-storage/canonical-merge) and counts processed.

**Why it matters:** Large P&L files can take 30+ seconds to parse and ingest. Blocking the HTTP request risks timeouts. Staff Engineers building robust enterprise integrations need async job tracking.

**Files likely to touch:** `backend/app/api/v1/ingest.py` (split into sync and async routes), `backend/app/services/ingest_service.py` (progress callback), `backend/app/db/repo.py` (ingestion_run status updates)

**Verification:** POST large ingest payload, immediately GET status → shows "running" + phase; wait → shows "completed" + record counts.

---

*Last updated: 2026-04-17*
*Context: FastAPI + Vue + SQLite, NL-to-SQL via planner/narrator, two JSON source ingestion, no hallucination architecture*