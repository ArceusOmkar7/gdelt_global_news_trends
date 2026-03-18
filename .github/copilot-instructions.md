# GNIEM — Copilot Instructions

This is the Global News Intelligence & Event Monitoring System, a geopolitical intelligence 
dashboard built on GDELT data. Read CONTEXT.md fully before suggesting anything.

## Hard rules — never violate these

- **NEVER write `SELECT *` against any BigQuery table.** Always use the explicit column list in CONTEXT.md §2.
- **NEVER query BigQuery without a SQLDATE partition filter** (integer, YYYYMMDD format).
- **NEVER run a BigQuery query without a `dry_run=True` pre-check** that asserts bytes < BQ_MAX_SCAN_BYTES.
- **NEVER query GKG through any user-facing API endpoint.** GKG is batch-only.
- **NEVER suggest Kafka, Airflow, Redis, PostgreSQL, or cloud Spark** — all excluded, see CONTEXT.md §11.
- **NEVER use Python `date` or `datetime` objects as BigQuery SQLDATE values** — cast to int: `int(d.strftime('%Y%m%d'))`.
- **Hot tier (< 90 days) = DuckDB on local Parquet. Cold tier (> 90 days) = BigQuery Events only.**

## Stack
- Backend: FastAPI + Pydantic v2, Python 3.11
- Hot tier: DuckDB (in-process, not a server)
- Cold tier: google-cloud-bigquery, guarded by dry_run
- Scripts: plain Python + cron/systemd (no Celery, no Airflow)
- Frontend: React + TypeScript + Vite, Mapbox GL JS, Recharts

## Current priority
Fix `backend/infrastructure/gdelt_repository.py` — add partition filters and column pruning.
Then add `backend/infrastructure/duckdb_repository.py` from scratch.