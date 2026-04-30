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

### Timeline Slider Infinite Update Loop
- **Symptom:** Frontend crashed/reloaded with `Maximum update depth exceeded` in `DateRangeSlider`.
- **Root Cause:** Effect-based bidirectional sync (`local slider state -> global dateRange -> effect -> local slider state`) created recursive updates.
- **Resolution:** Removed effect-driven writeback; only commit date-range updates from explicit user actions (handle drag/preset click) with equality guards.

### Duplicate Initial Query Burst on Startup
- **Symptom:** Non-anomaly cards felt slow relative to anomalies, especially on first paint.
- **Root Cause:** Date-dependent queries fired once with default range and again after hot-tier date alignment.
- **Resolution:** Added global `dateWindowReady` gate so date-dependent queries wait until alignment/fallback is complete.

### Briefings Generated But Not Visible in UI
- **Symptom:** `briefings.json` had entries, but frontend did not display them.
- **Root Cause:** No backend briefing endpoint and no frontend query/render path.
- **Resolution:** Added `GET /api/v1/analytics/briefings`, frontend API/types integration, and Nightly Briefing section in Regional Dossier.

### Anomaly Country Names Missing in Card Rows
- **Symptom:** Anomaly rows showed raw country codes only.
- **Root Cause:** Backend `AnomalyEntry` schema omitted `country_name/country_display`, stripping fields from response model.
- **Resolution:** Added display/name fields to schema and standardized frontend formatting as `Country Name (CC)`.

### Apify Scraper Parameter TypeError
- **Symptom:** The backend failed when calling the Apify API due to an invalid parameter for wait duration, causing scraping to fail.
- **Root Cause:** Apify client expected `wait_secs` but was passed `wait_duration` which was removed or unsupported.
- **Resolution:** Changed `wait_duration=timedelta(...)` to `wait_secs=self._slow_timeout_seconds` in `scraper_service.py`. Added `waitForFinish: 5000` parameter in the payload.

### Conflict Forecast Chart — Black Band in Light Mode
- **Symptom:** In light mode, the AreaChart conflict forecast displayed a large black rectangle covering the lower half of the chart.
- **Root Cause:** Recharts stacked area uses a "clip" approach — the lower boundary area is filled with the background colour to mask the band. The hardcoded `fill="rgba(10,10,10,0.8)"` (near-black) was used as the clip colour, which is correct for dark mode but visible as a solid black band on a light background.
- **Resolution:** Made the clip fill theme-aware via the `ct` (chart-token) object: `ct.clipFill` is `rgba(10,10,10,0.85)` in dark mode and `rgba(248,250,252,1)` (the light background colour) in light mode. Applied to `IntelligencePanel.tsx`.

### Intelligence Panel Stays Scrolled to Bottom After Event Navigation
- **Symptom:** When navigating from the country/regional view to an event detail view (clicking an event link in Top Events), the panel content appeared scrolled to the bottom, hiding the event header.
- **Root Cause:** The `<div>` containing both the regional and event views shares a single scroll container. Switching from the (taller) regional view to the event view preserved the existing `scrollTop`, landing mid-page.
- **Resolution:** Added `scrollRef = useRef<HTMLDivElement>()` on the scrollable container and a `useEffect` that resets `scrollRef.current.scrollTop = 0` whenever `selectedEvent` changes.

### CAMEO Codes Don't Cover Sports / Tech / Health Topics
- **Symptom:** The category filter for SPORTS, TECH, and HEALTH returns irrelevant events or low volumes because GDELT's CAMEO taxonomy is actor-action based (who does what to whom), not topic-based.
- **Root Cause:** CAMEO root codes like `01` (public statement), `05` (diplomacy) describe *interaction types*, not news topics. No CAMEO root code means "sports" or "technology".
- **Resolution (partial):** Approximate mappings used for now (e.g., `TECH` → code `03` Cooperation, `SPORTS` → code `01`). Full fix requires filtering on the GKG `themes` column using GCAM/GDELT theme codes (e.g., `HEALTH_*`, `SPORTS_*`). Documented as pending technical debt.

### Cold-Tier Monthly Query Limit Too Restrictive for Development
- **Symptom:** Development/testing sessions exhausted the cold-tier 100 query/month cap quickly, blocking further queries.
- **Root Cause:** `cold_tier_monthly_query_limit` was set to `le=100` in settings, appropriate for production but not development.
- **Resolution:** Raised `le` constraint to `999999` and `default` to `999999` in `settings.py` for development use. Production config should be adjusted separately.

