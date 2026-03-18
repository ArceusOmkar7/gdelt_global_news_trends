# GNIEM Project — Gemini CLI Context

Read CONTEXT.md for full architecture. This file is a quick-start summary.

## What this project is
A geopolitical intelligence dashboard on GCP, backed by GDELT data. 
FastAPI backend + React/Mapbox frontend. 3-person student project, ~3 months to deadline.

## Critical cost safety rules
1. Every BigQuery query MUST have `WHERE SQLDATE >= <int>` partition filter
2. Every BigQuery query MUST run dry_run=True first, assert bytes < 2_000_000_000
3. Never SELECT * from BigQuery — column list in CONTEXT.md §2
4. GKG table: treat as a landmine. 3.6 TB, $17.50/accidental scan.

## Current state (March 2026)
- Backend (FastAPI + BigQuery): exists but has full-table-scan bug in gdelt_repository.py
- Hot tier (DuckDB + Parquet): not yet built — needs duckdb_repository.py
- Frontend (React/Mapbox): partially built
- Scripts (cron jobs): not yet written

## Immediate task
Fix gdelt_repository.py, then build duckdb_repository.py. See CONTEXT.md §13 for code patterns.