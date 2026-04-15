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

## Frontend Query Flow
- **Date alignment:** On app bootstrap, date range is aligned to latest hot-tier `last_updated_at` when local data lags behind current date.
- **Readiness gate:** `dateWindowReady` gates date-dependent queries (`map`, `global-pulse`, `top-threat`, regional dossier queries) to avoid duplicate stale+aligned fetch cycles.
- **Timeline control:** Bottom `Timeline Window` slider drives global `dateRange` in Zustand.

## Analytics Cache Endpoints
- `GET /api/v1/analytics/anomalies` -> serves `data/cache/anomalies.json`.
- `GET /api/v1/analytics/briefings` -> serves `data/cache/briefings.json`.
- `GET /api/v1/analytics/spikes` -> computed from hot-tier parquet with in-process TTL cache.

## Tier Model & Routing
- **Hot Tier:** Data within last 90 days (DuckDB + Parquet).
- **Cold Tier:** Data older than 90 days (BigQuery, Events table ONLY).
- **Cold Tier Limits:** Max 30-day window per query, max 3 queries/user/month.
- **AI Briefings:** Served from pre-computed JSON cache or live Groq API (fallback).

## Environment Variables
- `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`
- `GDELT_DATASET` (gdelt-bq.gdeltv2)
- `HOT_TIER_PATH` (/data/hot_tier), `CACHE_PATH` (/data/cache)
- `GROQ_API_KEY`, `MAPBOX_TOKEN`
- `BQ_MAX_SCAN_BYTES` (2,000,000,000)

## What NOT to use
- **Kafka/Airflow/Spark (Cloud):** Too heavy for e2-standard-2 (8GB RAM). Use cron and DuckDB.
- **PostgreSQL/Cloud SQL:** Unnecessary cost. DuckDB handles OLAP efficiently.
- **Redis:** DuckDB's internal metadata caching is sufficient.
