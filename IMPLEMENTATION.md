# Finance Insights AI — Implementation Plan

## Goal
Build a small system that ingests two provided JSON P&L sources, normalizes them into a single monthly “source of truth” in SQLite, exposes clean REST APIs, and supports natural-language querying (NLQ) + insight narratives via the OpenAI API.

## Scope (keep it simple)
- Focus on **Profit & Loss (P&L)** only (monthly + quarterly/yearly aggregations).
- **Deterministic data + metrics** live in SQLite; the LLM is used for **intent parsing + narrative** (never “make up” numbers).
- No vector DB, no complex ETL orchestration, no streaming ingestion.

---

## Data Sources (what we’re integrating)

### `data1.json` (QuickBooks-style P&L report)
Observed structure:
- Top-level: `{ "data": { "Header": ..., "Columns": {"Column": [...]}, "Rows": {"Row": [...] } } }`
- Columns include month buckets (e.g., `Jan 2020` … `Aug 2025`) and a `Total` column.
- Top-level sections found: `Income`, `Cost of Goods Sold`, `Expenses`, `Other Income`, `Other Expenses`.
- Summary “groups” exist as rows with `group` like: `GrossProfit`, `NetOperatingIncome`, `NetOtherIncome`, `NetIncome`.

Key implication:
- We can reliably derive **monthly metrics** (e.g., Net Income per month) from the **Summary** rows.
- We can also extract **leaf line items** from the hierarchical Rows tree for “expense category increase” questions.

### `data2.json` (Rootfi-style monthly P&L)
Observed structure:
- Top-level: `{ "data": [ {period_start, period_end, revenue: [...], cost_of_goods_sold: [...], operating_expenses: [...], gross_profit, net_profit, ...}, ... ] }`
- `data` is a list of **monthly periods** (36 months: `2022-08` → `2025-07`).
- `revenue`, `cost_of_goods_sold`, `operating_expenses`, `non_operating_revenue`, `non_operating_expenses` are **nested trees** of `{name, value, account_id?, line_items:[...]}`.
- Scalar metrics include `gross_profit`, `operating_profit`, `net_profit` (and some nullable fields like `taxes`).

Key implication:
- We can ingest both **period-level metrics** and **leaf line items** for breakdown/trend questions.
- The period range overlaps with `data1.json` (`2022-08` → `2025-07`), so we merge and reconcile overlaps into one canonical dataset.

---

## Canonical Model (single source of truth)
Normalize everything to **monthly periods** with:
1) **Monthly metrics** (for fast NLQ/analysis)
2) **Monthly line items (leaf-level)** (for category questions)

### Canonical metric names
We’ll standardize to these metric identifiers (stored as rows, not columns):
- `revenue_total`
- `cogs_total`
- `gross_profit`
- `operating_expenses_total`
- `operating_profit`
- `non_operating_revenue_total`
- `non_operating_expenses_total`
- `taxes_total`
- `net_income` (canonical profit)

Source mapping:
- QuickBooks `Net Income` → `net_income`
- Rootfi `net_profit` → `net_income`

### Canonical categories (for line items)
- `revenue`
- `cogs`
- `operating_expense`
- `non_operating_revenue`
- `non_operating_expense`
- `other_income` / `other_expense` (QuickBooks naming)
- `unknown`

Line item identity:
- `path`: a stable hierarchy string, e.g. `Income > revenue_stream_5 > operations_expense_6`
- `name`: leaf label (last segment)
- `account_id`: nullable (present in Rootfi trees)

### Merging strategy (single source of truth)
We ingest both JSONs and **merge them into one canonical dataset** used by all APIs.

Merge rules (kept deterministic and simple):
- Build canonical `period` rows as the union of months across both sources.
- Store all parsed values as **raw observations** with `source = quickbooks|rootfi`.
- Build canonical metrics (`metric_value`) per period/metric:
  - If only one source has a value → use it.
  - If both sources have a value → if they’re within a tolerance, use the configured “primary” source and record provenance `quickbooks+rootfi`; otherwise use the primary source and log a reconciliation issue with both values.
- Canonical line items (`line_item_value`) follow the same idea, but we do **not** attempt fuzzy matching across taxonomies; we select one source per period/category (with fallback) to avoid double counting.

---

## Simple Pipeline Architecture

### High-level flow
```
            ┌───────────┐          ┌─────────────────┐          ┌──────────────┐
 data1.json │ QuickBooks │──raw───▶ │                 │──canon─▶ │              │
───────────▶│  Adapter   │ facts    │ Merge/Reconcile │  facts   │    SQLite     │──▶ REST APIs
            └───────────┘          │                 │          │ (source of    │──▶ NLQ tools
            ┌──────────┐           └─────────────────┘          │   truth)      │        │
 data2.json │  Rootfi   │──raw─────────────────────────────────▶│              │        ▼
───────────▶│ Adapter   │ facts                                  └──────────────┘     OpenAI API
            └──────────┘                                                           │
                                                                                   ▼
                                                                              Final answer

 Vue 3 UI ─────────────────────────────────────────────────────────▲
 (Chat + Metrics)                 calls REST endpoints
```

### Pipeline stages (minimal)
1. **Ingest**: parse both JSON formats into raw observations.
2. **Validate**: basic sanity checks + warnings (don’t hard-fail unless data is unusable).
3. **Merge/Reconcile**: combine overlaps into canonical metrics + line items.
4. **Persist**: upsert canonical periods/metrics/line-items into SQLite.
5. **NLQ**: LLM uses tools to fetch facts, then narrates.

---

## Backend Design (FastAPI + SQLite)

### Suggested folder layout
```
backend/
  app/
    main.py
    api/
      v1/
        chat.py
        metrics.py
        ingest.py
    adapters/
      quickbooks_pnl.py
      rootfi_pnl.py
    db/
      sqlite.py
      schema.sql
      repo.py
    services/
      ingest_service.py
      query_service.py
      nlq_service.py
    core/
      settings.py
      logging.py
      errors.py
  tests/
```

### Database schema (SQLite)
Keep schema small and query-friendly.

Implementation detail (no ORM):
- Use Python’s built-in `sqlite3` with a per-request connection (or a small connection manager).
- Create tables by executing `db/schema.sql` on app startup (idempotent `CREATE TABLE IF NOT EXISTS`).
- Prefer parameterized SQL in `db/repo.py`; return Pydantic response models from the service layer.

1) `period` (canonical month)
- `id` (PK)
- `period_start` (DATE)
- `period_end` (DATE)
- `currency` (TEXT, nullable)
- Unique: (`period_start`, `period_end`)

2) `raw_metric_value` (per-source observations)
- `id` (PK)
- `period_id` (FK → period)
- `source` (`quickbooks` | `rootfi`)
- `metric` (TEXT)
- `value` (REAL)
- Unique: (`period_id`, `source`, `metric`)

3) `raw_line_item_value` (per-source observations)
- `id` (PK)
- `period_id` (FK → period)
- `source` (`quickbooks` | `rootfi`)
- `category` (TEXT)
- `path` (TEXT)
- `name` (TEXT)
- `account_id` (TEXT, nullable)
- `value` (REAL)
- Unique: (`period_id`, `source`, `category`, `path`)

4) `metric_value` (canonical merged)
- `id` (PK)
- `period_id` (FK → period)
- `metric` (TEXT)
- `value` (REAL)
- `provenance` (TEXT, e.g. `quickbooks`, `rootfi`, `quickbooks+rootfi`)
- Unique: (`period_id`, `metric`)

5) `line_item_value` (canonical merged)
- `id` (PK)
- `period_id` (FK → period)
- `category` (TEXT)
- `path` (TEXT)
- `name` (TEXT)
- `account_id` (TEXT, nullable)
- `value` (REAL)
- `provenance` (TEXT, e.g. `quickbooks`, `rootfi`)
- Unique: (`period_id`, `category`, `path`)

6) (For conversation follow-ups) `chat_session` + `chat_message`
- `chat_session`: `id`, `created_at`
- `chat_message`: `session_id`, `role`, `content`, `created_at`

7) (Optional but helpful) `ingestion_run` + `ingestion_issue`
- Store warnings like missing values, reconciliation deltas, parse failures (including per-metric source mismatches).

### Ingestion adapters

**QuickBooks adapter (`data1.json`)**
- Read `Columns.Column` to map column index → month (ignore `Total` for monthly inserts; store it as a separate “all-time total” only if needed).
- Walk `Rows.Row` recursively:
  - Track section path (e.g., `Income > revenue_stream_5`).
  - For each `type == "Data"` row with `ColData`:
    - `ColData[0].value` is the line label.
    - Remaining `ColData[i].value` map to month columns.
    - Empty string → treat as `0.0` (and log a warning if desired).
- Upsert canonical `period` rows for each month column.
- Parse Summary group rows (Gross Profit, Net Income, etc.) into `raw_metric_value` with `source=quickbooks`:
  - `Net Income` → `net_income`
  - `Gross Profit` → `gross_profit`
  - (Optionally store `net_operating_income`, `net_other_income` too)
- Store flattened leaf line items into `raw_line_item_value` with `source=quickbooks`.

**Rootfi adapter (`data2.json`)**
- For each period object:
  - Upsert canonical `period` record (`period_start`, `period_end`).
  - Store scalar metrics into `raw_metric_value` with `source=rootfi` where present:
    - `gross_profit`, `operating_profit`, `net_profit → net_income`
  - Flatten each category tree (`revenue`, `cost_of_goods_sold`, `operating_expenses`, `non_operating_revenue`, `non_operating_expenses`) into **leaf** line items:
    - Leaf = node with no `line_items`.
    - Store `path`, `name`, `account_id`, `value` into `raw_line_item_value` with `source=rootfi`.
  - Also store totals as `raw_metric_value` by summing leaf nodes:
    - `revenue_total`, `cogs_total`, `operating_expenses_total`, etc.

**Merge/Reconcile (build canonical tables)**
- Run after both sources are ingested (or on every ingestion run).
- Metrics: for each (`period`, `metric`), pick a canonical `value` using the configured primary source + tolerance check; write to `metric_value` with `provenance`.
- Line items: for each (`period`, `category`), select one source (primary if present, else fallback) and copy that source’s items into `line_item_value` with `provenance`.

### Validation rules (basic, not brittle)
- Date parsing: ensure `period_start <= period_end`.
- Type checks: numbers must parse to float.
- Currency consistency:
  - QuickBooks has `Header.Currency`.
  - Rootfi may have `currency_id` null; treat as unknown.
- Optional reconciliation:
  - Sum leaf nodes vs top node values (Rootfi trees) within a tolerance (e.g., 0.5–1.0 currency units).

---

## REST API (practical endpoints)
Namespace suggestion: `/api/v1/...`

### Ingestion
- `POST /api/v1/ingest`
  - Body: `{ "mode": "replace"|"upsert" }`
  - Default behavior for the exercise: read bundled `data1.json` + `data2.json`, ingest both into raw tables, then rebuild canonical merged tables.
  - Merge config (env): `PRIMARY_SOURCE` (`quickbooks`|`rootfi`), `MERGE_TOLERANCE` (e.g., `1.0` absolute or `0.01` as 1%).

### Periods
- `GET /api/v1/periods?include_provenance=true|false`
  - Returns available months (and optional coverage/provenance).

### Metrics
- `GET /api/v1/metrics/timeseries?metric=net_income&start=2024-01-01&end=2024-12-31&group_by=month|quarter|year&include_provenance=true|false`
- `GET /api/v1/metrics/compare?metric=net_income&period_a=2024-Q1&period_b=2024-Q2`

### Breakdown
- `GET /api/v1/breakdown?category=operating_expense&start=2024-01-01&end=2024-12-31&level=1|2|3&include_provenance=true|false`
  - `level` controls how many path segments to aggregate.

### Natural language chat
- `POST /api/v1/chat`
  - Body: `{ "session_id": "optional", "message": "..." }`
  - Returns:
    - `session_id`
    - `answer` (string)
    - `supporting_data` (structured: totals, timeseries, breakdown tables)
    - `tool_calls` (optional: names + args for debugging/demo)

---

## AI/NLQ Design (OpenAI API)

### Principle
- The LLM does **planning + narration**.
- The backend does **all computations**.
- The LLM only sees:
  - metric definitions
  - available periods
  - tool outputs (numbers)

### Minimal tool set (function calling)
Define 3–5 tools max to keep it robust.

1) `list_periods()`
- Returns: available months/quarters/years.

2) `query_metric(metric, start_date, end_date, group_by, include_provenance=false)`
- Returns: `{ total, series:[{period,value,provenance?}], currency }`

3) `query_breakdown(category, start_date, end_date, level, include_provenance=false)`
- Returns: `{ rows:[{name,value,share,provenance?}], currency }`

4) `compare_periods(metric, period_a, period_b, include_provenance=false)`
- Returns: `{ a_value, b_value, delta_abs, delta_pct }`

### Conversation handling (follow-ups)
- Frontend holds `session_id`.
- Backend stores last N messages per session and passes them to the model.
- If the user asks “What about Q2?”, the model uses context + `list_periods` to resolve.

### Output style requirements
In the system prompt:
- “If you don’t have the data, ask a clarifying question.”
- “Never invent numbers; only use tool outputs.”
- “Answer concisely; include 1–3 key supporting facts.”

---

## Frontend (Vue 3)

### Pages
1) **Chat** (primary demo)
- Prompt input
- Message list
- Optional “Show data” panel that renders `supporting_data` tables/series.

2) **Metrics** (simple exploration)
- Metric selector (net income, revenue, expenses)
- Date range
- Timeseries chart (Chart.js) + table
- Optional provenance toggle (shows where values came from)

### Suggested structure
```
frontend/
  src/
    api/client.ts
    pages/Chat.vue
    pages/Metrics.vue
    components/ChatThread.vue
    components/MetricChart.vue
    router/index.ts
```

---

## Implementation Steps (milestones)
1) Scaffold backend (`backend/`) with FastAPI, settings, SQLite schema + connection.
2) Implement adapters:
   - QuickBooks report parser → raw observations (metrics + leaf line items)
   - Rootfi period+tree parser → raw observations (metrics + leaf line items)
3) Build ingestion service + `/ingest` endpoint to load both sources and rebuild canonical merged tables.
4) Build query service + metrics/breakdown endpoints.
5) Add NLQ service with OpenAI tool calling + `/chat` endpoint.
6) Scaffold Vue 3 frontend (plain CSS) with Chat + Metrics pages (Chart.js).
7) Add tests for parsers and key query functions.
8) Add README + simple deploy config (Render).

---

## Deployment (demo-friendly)
- Backend: Render.com web service
  - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Env: `OPENAI_API_KEY`, `DB_PATH` (e.g., `./app.db`)
- Frontend: Render static site / Netlify / Vercel
  - Env: `VITE_API_BASE_URL`
- Enable CORS in FastAPI for the frontend origin.

---

## Confirmed Choices
- Database: SQLite (no ORM)
- Frontend styling: plain CSS
- Charts: Chart.js
- Data integration: single merged source of truth (both JSONs merged into canonical tables)
- Optional “B” analytics: deferred (backlog)
