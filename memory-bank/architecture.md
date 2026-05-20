# GNIEM Architecture & Safety Rules

## Full Stack Overview
- **Backend:** FastAPI (Python) + DuckDB (In-process OLAP) + BigQuery (Cold Tier).
- **Frontend:** React + Vite + TypeScript + Mapbox GL JS + Zustand (State) + Recharts.
- **Infrastructure:** GCP VM (e2-standard-2, Ubuntu 22.04) + Nginx + Vercel (Frontend).
- **Data Source:** GDELT 2.1 (Events, GKG, Mentions).

## BigQuery Safety Rules (CRITICAL)
- **Table IDs:**
  - `gdelt-bq.gdeltv2.events` (partitioned by `SQLDATE` integer)
  - `gdelt-bq.gdeltv2.gkg` (partitioned by `DATE` integer)
  - `gdelt-bq.gdeltv2.eventmentions` (partitioned by `SQLDATE` integer)
- **Mandatory Query Pattern:**
  - Always filter by `SQLDATE` using integer comparison (e.g., `WHERE SQLDATE >= 20250101`).
  - Never use `SELECT *`; always use an explicit column list.
  - Always run `dry_run=True` first and assert `total_bytes_processed < 2,000,000,000`.
- **GKG Table:** 3.6 TB. Never query without a date partition. Full scan costs ~$17.50.

## DuckDB Patterns
- **Concurrency (current implementation):** Use fresh per-query DuckDB `:memory:` connections to avoid shared-connection contention under concurrent requests.
- **Latency behavior:** First uncached requests are parquet-scan bound; warm responses are primarily API/cache bound.
- **Data Source:** Querying local Parquet files in `/data/hot_tier/`.

### Top-people query notes
- The `/api/v1/events/top-people` endpoint aggregates people from the GKG `persons` array. By design the default metric is `SUM(NumMentions)` (total mentions across events), not distinct articles or event-counts. This can produce totals larger than the number of events because a single article/event can contain multiple mentions of the same person.
- Performance optimisations applied:
  - Predicate pushdown: filters (date, country, theme, event root codes) are applied in a subquery before `UNNEST(persons)` to avoid exploding arrays and reduce I/O.
  - Non-empty array check (`persons <> []`) is used to skip rows with no persons.
  - Responses are cached in-process for identical filter sets for `_PEOPLE_TTL` seconds (default 120s) to avoid repeated UNNEST/aggregation runs.
- Recommended next steps: persistent disk cache (under `CACHE_PATH/top_people/`), nightly precompute of top people per (date,country,theme) to serve the dashboard instantly, or expose a lighter `metric` parameter (mentions|events|rows) so the frontend can request cheaper counts when needed.

## Frontend Query Flow
- **Date alignment:** On app bootstrap, date range is aligned to latest hot-tier `last_updated_at` when local data lags behind current date.
- **Readiness gate:** `dateWindowReady` gates date-dependent queries (`map`, `global-pulse`, `top-threat`, regional dossier queries) to avoid duplicate stale+aligned fetch cycles.
- **Timeline control:** Date range launched via a header popover button (not a bottom slider). Global `dateRange` in Zustand drives all queries.
- **Category filtering:** `activeCategory` maps to `eventRootCode` via `CATEGORY_TO_ROOT_CODE` dict. ALL → null (no filter). Category → CAMEO root code sent as query param to `/global-pulse` and `/events` endpoints.
- **Theme:** `isDarkTheme` boolean in Zustand. `useEffect` in `App.tsx` sets `document.documentElement.setAttribute('data-theme', ...)`. CSS variables in `index.css` remap surface/accent colours for light mode. Charts use a `ct` (chart-token) object derived from `isDarkTheme` for all axis/fill/tooltip colours.

## Analytics Cache Endpoints
- `GET /api/v1/analytics/anomalies` → serves `data/cache/anomalies.json`.
- `GET /api/v1/analytics/briefings` → serves `data/cache/briefings.json`.
- `GET /api/v1/analytics/spikes` → computed from hot-tier parquet with in-process TTL cache.
- `GET /api/v1/events/daily-trend` → per-day `{date, total, conflict}` from DuckDB. `conflict = QuadClass >= 3`. Accepts `start_date`, `end_date`, `event_root_code`.
- `GET /api/v1/events/global-pulse` → KPI aggregate (total events, most active/hostile country, avg tone, conflict ratio). Accepts `event_root_code` for category filtering.

## Tier Model & Routing
- **Hot Tier:** Data within last 90 days (DuckDB + Parquet).
- **Cold Tier:** Data older than 90 days (BigQuery, Events table ONLY).
- **Cold Tier Limits:** Max 30-day window per query, max 999999 queries/user/month (effectively unlimited).
- **AI Briefings:** Served from pre-computed JSON cache or live Groq API (fallback).
- **On-demand article analysis:** Apify actor runs extract article text, then Groq summarizes and structures the findings.

## Dashboard UI Architecture
- **Main layout:** `App.tsx` controls view mode (`dashboard` | `map`) and active category.
- **Category system:** `CATEGORIES = ['ALL','WAR','POLITICS','ECONOMY','SPORTS','TECH','HEALTH']`. Each maps to a CAMEO root code (or `null` for ALL) via `CATEGORY_TO_ROOT_CODE`.
- **Bento grid:** ALL view → TopThreatCard (col-span 8) + SpikeAlertsCard (col-span 4). Category view → full-width TrendingNewsFeed.
- **EventTrendChart:** Placed between KPI row and bento grid. Stacked Recharts AreaChart — outer area = total events, inner area = conflict events (QuadClass ≥ 3).
- **System Panel:** Slide-in right drawer triggered by `[ ⌘ System ]` header button. `showSystemPanel` local state. Blurred backdrop dismisses on click.
- **Map launch card:** `map-launch-card` CSS class. Always uses the same dark cyber card design in both light and dark themes.

## Environment Variables
- `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`
- `GDELT_DATASET` (gdelt-bq.gdeltv2)
- `HOT_TIER_PATH` (/data/hot_tier), `CACHE_PATH` (/data/cache)
- `GROQ_API_KEY`, `APIFY_API_TOKEN`, `MAPBOX_TOKEN`
- `BQ_MAX_SCAN_BYTES` (2,000,000,000)

## What NOT to use
- **Kafka/Airflow/Spark (Cloud):** Too heavy for e2-standard-2 (8GB RAM). Use cron and DuckDB.
- **PostgreSQL/Cloud SQL:** Unnecessary cost. DuckDB handles OLAP efficiently.
- **Redis:** DuckDB's internal metadata caching is sufficient.
