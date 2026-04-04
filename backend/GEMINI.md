# Backend Mandates — GNIEM

## DuckDB Guidelines
- **Concurrency:** Open a fresh `:memory:` connection for EVERY query.
- **Pattern:** `conn = duckdb.connect(database=":memory:"); try: ... finally: conn.close()`.
- **Shared State:** Never use `self._conn` or global connection objects.

## BigQuery Safety (MANDATORY)
- **Dry Run:** Always set `dry_run=True` before executing any query.
- **Cost Assert:** Assert `dry_run_job.total_bytes_processed < BQ_MAX_SCAN_BYTES`.
- **Filtering:** Always include `WHERE SQLDATE >= {YYYYMMDD}`.
- **Selection:** Always provide an explicit column list. Never use `SELECT *`.

## AI & External APIs
- **Groq:** Implement 3-attempt exponential backoff (1s, 2s, 4s). Never return an empty string on failure.
- **Forecasting:** Prophet models require at least 7 days of historical data. Pre-compute nightly.

## Cache Pattern
- **Implementation:** In-process dictionary with timestamps.
- **TTL:** 1 hour for analytics/clusters, 15 minutes for activity spikes.
- **Routing:** Use `RoutedRepository` to manage hot/cold tier switching.

## Cold Tier Policy
- **Tables:** Events table ONLY. Never GKG or Mentions.
- **Window:** Maximum 30-day date range per query.
- **Quota:** Maximum 3 cold queries per user per month.
