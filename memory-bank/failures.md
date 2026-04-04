# Known Failures & Resolutions — GNIEM

### GKG Full Table Scan
- **Symptom:** Accidentally scanning the 3.6 TB GKG table costs ~$17.50 per query.
- **Resolution:** Mandatory `dry_run=True` and `BQ_MAX_SCAN_BYTES` (2GB) limit in all BigQuery calls. Strict requirement for date partitioning in SQL.

### Shared DuckDB Connection Serializing
- **Symptom:** Multiple simultaneous dashboard queries (e.g., Regional Dossier) appeared stuck or slow.
- **Resolution:** Abandoned shared `self._conn` with locks. Now use per-query fresh `:memory:` connections to allow parallel execution.

### Groq Silent Failures
- **Symptom:** Groq API occasionally fails silently or returns empty strings.
- **Resolution:** Implemented 3-attempt exponential backoff (1s/2s/4s). Never return empty strings; use deterministic fallback text if all attempts fail.

### FIPS Code "WE" in Cluster Clicks
- **Symptom:** Clicking regional aggregate codes like "WE" (Western Europe) results in empty dossiers.
- **Resolution:** GDELT uses FIPS codes. Real country codes work, but regional aggregates are currently unsupported in dossier views. (Known limitation).

### SQLDATE Integer Parsing Duplication
- **Symptom:** `SQLDATE` (YYYYMMDD) integer parsing logic was duplicated across multiple locations, leading to drift.
- **Resolution:** Centralized date-to-int and int-to-date logic in shared utility functions.

### Unbounded In-process Cache Growth
- **Symptom:** Memory usage creeped up over time due to uncapped dict-based caches.
- **Resolution:** Implemented TTL (1hr for analytics, 15min for spikes) and size limits on all in-memory caches.

### Risk Score Threshold Duplication
- **Symptom:** Color thresholds (Green/Amber/Red) were inconsistent between Python backend and TypeScript frontend.
- **Resolution:** Hardcoded shared thresholds: LOW 0-30 (Green), MODERATE 31-50 (Amber), ELEVATED 51-70 (Orange), CRITICAL 71-100 (Red).

### GDELT 2.1 Export Index Misalignment
- **Symptom:** Realtime fetcher produced corrupted country codes (single digits) and incorrect coordinates.
- **Resolution:** Updated `scripts/realtime_fetcher.py` with exact zero-based indices from GDELT 2.1 schema (ActionGeo_CountryCode=53, etc). Cleared `realtime_buffer.parquet`.

### Missing Repository Methods causing 500 + CORS Errors
- **Symptom:** Frontend console showed CORS blocks on `/analytics/spikes` and `/analytics/anomalies`. Backend logs showed `AttributeError: 'DuckDbRepository' object has no attribute 'get_activity_spikes'`.
- **Resolution:** Implemented `get_activity_spikes` and `get_anomalies` in `DuckDbRepository`. Corrected the 500 error, which allowed the CORS middleware to function normally.
