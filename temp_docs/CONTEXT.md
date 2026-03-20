# GNIEM — Project Context & Architecture Reference

> **For AI assistants:** This file is the single source of truth for the GNIEM project. Read it fully before generating any code, queries, configs, or documentation. Do not assume anything not stated here.

---

## 1. Project Identity

**Full name:** Global News Intelligence & Event Monitoring System (GNIEM)
**Course:** AI, Cloud and Big Data — Navrachana University, Vadodara
**Team size:** 3 members
**Deadline:** ~3 months from March 2026
**Evaluation:** Live deployment at URL + written reports (Cloud Cost Estimation, AI Requirements, Dataset Documentation) + 5V Big Data justification

---

## 2. Data Source: GDELT 2.1

GDELT (Global Database of Events, Language, and Tone) is a free, open dataset that monitors the world's news media in real time.

### Three tables used

| Table | What it contains | Access method |
|---|---|---|
| **Events** | Structured geopolitical events. CAMEO-coded actors, actions, locations, Goldstein scale, avg tone. ~60 columns. | BigQuery public dataset + 15-min CSV feed |
| **GKG** (Global Knowledge Graph) | Semi-structured. Themes, persons, organizations, tone, source URLs per news article. | BigQuery public dataset |
| **Mentions** | Each article that mentions each event. Confidence scores, article URLs. | BigQuery public dataset (optional) |

### BigQuery identifiers (CRITICAL — these are the correct table refs)
```
gdelt-bq.gdeltv2.events          -- partitioned by SQLDATE (YYYYMMDD integer, NOT a date type)
gdelt-bq.gdeltv2.gkg             -- partitioned by DATE (YYYYMMDD integer)
gdelt-bq.gdeltv2.eventmentions   -- partitioned by SQLDATE
```

### GDELT Events — key columns to SELECT (never SELECT *)
```
GLOBALEVENTID, SQLDATE, MonthYear, Year,
Actor1CountryCode, Actor2CountryCode,
Actor1Type1Code, Actor2Type1Code,
EventCode, EventBaseCode, EventRootCode,
QuadClass, GoldsteinScale, NumMentions, NumSources, AvgTone,
Actor1Geo_CountryCode, Actor2Geo_CountryCode,
ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long,
SOURCEURL
```
**Do NOT select:** Actor1Name, Actor2Name, Actor1Geo_FullName, Actor2Geo_FullName, MentionDocLen, or any column not in the list above, unless explicitly required. Every extra column costs money in BigQuery.

### BigQuery query safety rules (MANDATORY)
1. **Always filter by SQLDATE** using integer comparison: `WHERE SQLDATE >= 20250101`
2. **Never use `BETWEEN` on SQLDATE** — use `>=` and `<` with integer literals
3. **Never `SELECT *`** — always explicit column list
4. **Wrap all BigQuery calls with cost estimation** using `dry_run=True` before executing
5. **Daily batch job max scan budget:** 2 GB per run (hard limit in code)
6. **Fallback queries only:** BigQuery is only queried for dates older than 90 days. All recent data comes from local Parquet.

### BigQuery scan cost analysis (per table, per query type)

**Critical distinction:** BigQuery charges per bytes *scanned*, not bytes returned. The partition filter limits scanning to only that day's rows (~250k events). Column pruning reduces bytes per row. The large "full table" numbers below only apply when you forget the partition filter.

**Table sizes — full scan vs properly guarded daily batch:**

| Table | Full table size | Full scan (no guards) | After col pruning + 1-day partition | Monthly (30 daily runs) |
|---|---|---|---|---|
| Events | ~63 GB | ~6 GB | **~7–15 MB/day** | ~300 MB |
| EventMentions | ~104 GB | ~10 GB | **~20–40 MB/day** | ~900 MB |
| GKG | ~3.6 TB | ~7.7 GB | **~200–500 MB/day** (blob cols) | ~12 GB |
| **All 3 combined** | | | | **~13–15 GB/month = ~1.5% of free quota** |

**GKG is uniquely dangerous despite the small daily number.** Without the DATE partition filter, one GKG query scans the full 3.6 TB table = ~$17.50 instantly. The `dry_run=True` guard and `BQ_MAX_SCAN_BYTES` env var exist specifically for this.

**Cold tier scan costs (Events only, spans multiple day-partitions):**

| Date range requested | Events scan per query | Safe? |
|---|---|---|
| 7 days | ~50–100 MB | ✓ Very safe |
| 30 days | ~200–450 MB | ✓ Yes |
| 90 days | ~600 MB–1.5 GB | ✓ Yes |
| All history (no filter!) | ~63 GB | ✗ Never |

**Monthly budget breakdown (normal operation):**
- Hot tier batch jobs (all 3 tables, daily): ~15 GB/month
- Cold tier user queries (Events only, 3/user/month × ~10 users, 30-day window): ~15 GB/month
- Total: ~30 GB — **3% of free 1 TB quota — $0**
- Worst case (100 users all hitting cold tier): ~160 GB — still $0

### 15-minute CSV feed (near-realtime — free, no BigQuery)
GDELT publishes new CSVs every 15 minutes at:
```
http://data.gdeltproject.org/gdeltv2/lastupdate.txt
```
This file lists the 3 latest file URLs (Events, Mentions, GKG). Download, parse, append to hot tier. This is the velocity source for the 5V argument.

---

## 3. Architecture Overview

### Tier model

```
[GDELT BigQuery]     [GDELT 15-min CSV Feed]     [GDELT GKG BigQuery]
       |                       |                          |
       v                       v                          |
[Daily BQ batch job]   [15-min CSV fetcher]              |
  (cron, 2am)          (systemd timer)                   |
       |                       |                          |
       +----------+------------+                          |
                  |                                       |
                  v                                       |
         [Parquet hot tier]              [Nightly AI jobs]
         90 days · ~40 GB               Prophet + Groq
         VM local SSD                   pre-compute cache
                  |                          |
                  +----------+---------------+
                             |
                             v
              [FastAPI + DuckDB (in-process)]
              Nginx reverse proxy on GCP VM
                             |
              +--------------+--------------+
              |              |              |
         [React +        [Vercel]       [GCS bucket]
          Mapbox]         CI/CD          Parquet backup
```

### Routing logic (inside FastAPI)
- Request for data **within last 90 days** → DuckDB query on local Parquet
- Request for data **older than 90 days** → BigQuery cold tier, **Events table only**, max 30-day window per query, max 3 queries per user per month
- AI briefing request → serve pre-computed JSON cache; fall back to live Groq API if cache miss
- Conflict forecast request → serve pre-computed Parquet results (never on-demand Prophet)
- **GKG is NEVER queried through the cold tier** — GKG only accessed during nightly hot tier batch job

---

## 4. Infrastructure

### GCP VM
- **Instance:** e2-standard-2 (2 vCPU, 8 GB RAM)
- **OS:** Ubuntu 22.04 LTS
- **Disk:** 100 GB Balanced Persistent Disk (40 GB for Parquet hot tier, rest for OS + app + logs) — **billed separately from compute by GCP**
- **Region:** us-central1
- **Billing:** Fully offset by $300 GCP student credits
- **Estimated cost without credits:** ~₹4,960/month (~$58.92 USD: compute $48.92 + disk $10.00)

### Services running on VM
| Service | How it runs | Port |
|---|---|---|
| FastAPI (Uvicorn) | systemd service | 8000 (internal) |
| Nginx | systemd service | 80/443 (public) |
| Daily BQ batch job | cron (2am UTC) | — |
| 15-min CSV fetcher | systemd timer | — |
| Nightly AI jobs | cron (3am UTC) | — |

**Not running on VM:** Airflow, Kafka, Spark, Redis, PostgreSQL. These are not needed and would OOM the instance.

### Scaling strategy
**Current (100 users):** Single VM, no load balancer, Nginx handles all traffic directly.
**At 5,000 users:** Manual scaling — upgrade VM to e2-standard-4, expand disk to 200 GB, add GCP Regional External Load Balancer. This is deliberate manual scaling, not auto-scaling or containerization. Do not describe it as containerized scaling in any report.

### Frontend
- **Framework:** React + Vite + TypeScript
- **Map:** Mapbox GL JS
- **Hosting:** Vercel Hobby tier (free, CI/CD from GitHub)
- **Env var:** `VITE_API_URL` points to VM's public IP / domain

### External APIs
| API | Purpose | Cost | Limit |
|---|---|---|---|
| Groq (Llama 3 70B) | LLM briefings | Free | 14,400 req/day |
| Mapbox | Map tiles | Free | 50k loads/month |
| BigQuery | Cold tier archive | Free | 1 TB scan/month |

---

## 5. Data Pipeline Details

### Daily BigQuery batch job (`scripts/daily_bq_pull.py`)
- Runs at 2am UTC via cron
- Queries previous day's GDELT events (SQLDATE = yesterday integer)
- Column-pruned to the exact list in Section 2
- Appends to `/data/hot_tier/events_YYYYMM.parquet` using PyArrow
- Hard limit: abort if estimated bytes > 2 GB
- On failure: logs error, sends no alert (check logs manually)
- CLI: `python scripts/daily_bq_pull.py --backfill-days 7` to bootstrap 7 days at once

### 15-minute CSV fetcher (`scripts/realtime_fetcher.py`)
- Runs every 15 min via systemd timer
- Fetches `lastupdate.txt`, parses the Events CSV URL
- Downloads, decompresses, parses into DataFrame
- Deduplicates by GLOBALEVENTID against last 1000 rows of hot tier
- Appends to `/data/hot_tier/realtime_buffer.parquet`
- Buffer is merged into monthly Parquet nightly

### Nightly AI jobs (`scripts/nightly_ai.py`)
- **Prophet forecasting:** Runs on hot tier aggregated by country + day, forecasts 30 days ahead for top 50 countries by event volume. Output: `/data/cache/forecasts.parquet`
- **Groq briefings:** For top 30 countries, sends last 7 days of event summary to Groq Llama 3 70B, stores result in `/data/cache/briefings.json`
- Runs at 3am UTC (after batch pull completes)
- **Must be run after backfilling** to get proper 30-day forecast horizon. With only 1-2 days of data Prophet will produce a very short forecast.

### Cold tier rules (MANDATORY — do not relax these)

1. **Events table only** — never query GKG or EventMentions through the cold tier.
2. **Maximum 30-day date window per cold query** — enforce in the API layer before the query is built.
3. **Maximum 3 cold queries per user per month** — track in a lightweight counter.
4. **Always use `dry_run=True`** before executing any cold query. Abort if estimated bytes > 2 GB.
5. **Cache cold results** — after a cold query runs, cache the result as a Parquet file keyed by `{country_code}_{start_date}_{end_date}`.
6. **Result of cold queries is Events-only data** — do not attempt to enrich cold results with GKG themes/persons/orgs.

---

## 6. Backend Structure (FastAPI + Clean Architecture)

```
backend/
├── api/
│   ├── main.py               # FastAPI app, lifespan, CORS
│   ├── routers/
│   │   ├── events.py         # GET /events, /events/region/{cc}, /events/counts, /events/region/{cc}/risk-score
│   │   ├── analytics.py      # GET /analytics/clusters, /analytics/forecast/{cc}
│   │   ├── map.py            # GET /events/map (zoom-adaptive, TTL cache)
│   │   └── health.py         # GET /health, /health/settings
│   └── schemas/schemas.py    # Pydantic response models
├── application/
│   └── use_cases/
│       ├── get_events.py
│       ├── cluster_events.py
│       ├── forecast_events.py
│       └── analyze_event.py
├── domain/
│   ├── models/event.py       # Event, EventFilter, ForecastResult, Briefing, MapEventDetail
│   └── ports/ports.py        # IEventRepository, IAIService interfaces
└── infrastructure/
    ├── config/settings.py
    ├── data_access/
    │   ├── duckdb_repository.py   # Hot tier queries — per-query fresh connections (no shared lock)
    │   ├── bigquery_client.py
    │   ├── gdelt_repository.py    # Cold tier BigQuery queries
    │   └── routed_repository.py   # Routes hot/cold, enforces cold-tier policy
    └── services/
        ├── llm_analysis_service.py
        └── scraper_service.py
```

### Key API endpoints
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/events/map` | Zoom-adaptive map data (aggregated or detailed) |
| GET | `/api/v1/events/region/{cc}` | Events for a country |
| GET | `/api/v1/events/region/{cc}/risk-score` | Country risk score (hot-tier DuckDB only) |
| GET | `/api/v1/events/region/{cc}/stats` | Top themes, persons, orgs for a country |
| GET | `/api/v1/events/counts/{cc}` | Daily event counts for charting |
| GET | `/api/v1/analytics/forecast/{cc}` | Prophet conflict forecast |
| GET | `/api/v1/analytics/clusters` | TF-IDF + KMeans event clusters |
| GET | `/api/v1/events/{id}/analyze` | LLM deep analysis of a single event |
| GET | `/api/v1/health` | Service health check |
| GET | `/api/v1/health/settings` | Runtime settings |

### Key dependencies
```
fastapi, uvicorn, pydantic-settings
duckdb
google-cloud-bigquery, pyarrow, pandas
scikit-learn (TF-IDF + KMeans clustering)
prophet (time-series forecasting)
httpx (async HTTP for CSV feed)
```

### Environment variables (`.env`)
```
GCP_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GDELT_DATASET=gdelt-bq.gdeltv2
HOT_TIER_PATH=/data/hot_tier
CACHE_PATH=/data/cache
GROQ_API_KEY=
MAPBOX_TOKEN=
ENVIRONMENT=production
BQ_MAX_SCAN_BYTES=2000000000
```

### DuckDB concurrency pattern (IMPORTANT)
DuckDB connections are **not** shared across threads. Each query opens a fresh `:memory:` connection, queries the parquet glob, and closes immediately. This allows FastAPI's thread pool to run multiple DuckDB queries in parallel without lock contention. Do NOT reintroduce a shared `self._conn` + `threading.Lock()` pattern — it caused all Regional Dossier queries (5 simultaneous) to serialize and appear stuck.

```python
def _query(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    conn = duckdb.connect(database=":memory:", read_only=False)
    try:
        result = conn.execute(sql, params)
        columns = [col[0] for col in (result.description or [])]
        values = result.fetchall()
    finally:
        conn.close()
    return [dict(zip(columns, row)) for row in values]
```

### Country Risk Score endpoint
- **Route:** `GET /api/v1/events/region/{country_code}/risk-score`
- **Hot-tier only** — calls `DuckDbRepository.get_risk_score()` directly, never routes through `RoutedRepository`
- **Formula (0–100, higher = more dangerous):**
```python
def compute_risk_score(conflict_ratio, avg_goldstein, avg_tone) -> int:
    goldstein_score = max(0, min(100, ((-avg_goldstein + 10) / 20) * 100))
    tone_score = max(0, min(100, ((-avg_tone + 30) / 60) * 100))
    conflict_score = conflict_ratio * 100
    return round(conflict_score * 0.4 + goldstein_score * 0.35 + tone_score * 0.25)
```
- Color coding: green < 30, amber 30–60, red > 60

### Known data quality issues
- `mentions_count` can be `None` in rows where the Mentions join had no match during `daily_bq_pull.py`. Always coerce: `int(row.get("mentions_count") or 0)` — do NOT use `row.get("mentions_count", 0)` which passes `None` through.
- GDELT `ActionGeo_CountryCode` uses FIPS codes, not ISO-2. Some values are regional aggregates (e.g. `WE` = Western Europe) rather than real countries. The map cluster click uses this code for `setSelectedCountry` — it works for real country codes but regional codes will return empty dossiers.

---

## 7. Frontend Structure (React + Vite)

```
frontend/src/
├── components/
│   ├── map/GlobalEventMap.tsx       # Mapbox map, zoom-adaptive, BBOX snapping
│   └── tables/
│       ├── IntelligencePanel.tsx    # Event Intelligence + Regional Dossier panel
│       └── SystemControlPanel.tsx   # Health, runtime settings, controls
├── lib/
│   └── gdelt-lookups.ts             # QUAD_CLASS_LABELS, CAMEO_ROOT_LABELS,
│                                    # ACTOR_TYPE_LABELS, cleanGkgTheme()
├── services/
│   └── api.ts                       # Typed API client (all fetch calls here)
├── store/
│   └── useStore.ts                  # Zustand store
└── types/
    └── index.ts                     # TypeScript interfaces for all API responses
```

### IntelligencePanel — two modes
**Event Intelligence** (when `selectedEvent` is set):
- QuadClass badge (colored by conflict type)
- Goldstein context bar with label
- CAMEO event type human-readable label
- Actor display with type lookup
- GKG themes (cleaned via `cleanGkgTheme()`), persons, organizations
- LLM Analyze button → calls `/events/{id}/analyze`

**Regional Dossier** (when `selectedCountry` is set, `selectedEvent` is null):
- Threat Level score card (0–100, color-coded)
- Event Frequency chart (Recharts LineChart, last 14 days, cyan)
- Conflict Forecast — 30 Day (Recharts AreaChart, red uncertainty band + predicted line)
- Top Regional Themes (cleaned GKG themes with counts)
- Key Entities — People
- Active Organizations
- Top Events in Sector (clickable, transitions to Event Intelligence view)

### Zustand store — critical ordering rule
When handling aggregate cluster clicks in `GlobalEventMap.tsx`, **always call `setSelectedEvent(null)` BEFORE `setSelectedCountry(code)`**. The `setSelectedEvent` action resets `selectedCountry` to `null` as a side effect — calling it after `setSelectedCountry` wipes the country selection.

```tsx
// CORRECT order in onMapClick aggregate handler:
setSelectedEvent(null);               // must be first
setSelectedCountry(props.country_code); // must be second
```

### GKG theme cleanup (`cleanGkgTheme` in `gdelt-lookups.ts`)
Strips machine-readable prefixes from raw GDELT GKG theme codes. Prefixes handled (order matters):
`WB_\d+_`, `CRISISLEX_C\d+_`, `CRISISLEX_`, `FNCACT_`, `EPU_POLICY_`, `EPU_`, `SOC_`, `ENV_`, `ECON_`, `MED_`, `TAX_`, `USPEC_`, `UNGP_`

Always deduplicate themes before rendering: `[...new Set(themes)].slice(0, 6)`

### Frontend types (`types/index.ts`)
All API response types are defined here. Key additions:
- `RiskScoreResponse` — score, trend, conflict_ratio, avg_goldstein, avg_tone, total_events
- `ForecastPoint` — date, predicted_count, lower_bound, upper_bound
- `ForecastResponse` — country_code, horizon_days, model_type, historical_summary, predictions

### API service (`services/api.ts`)
All fetch calls go through `apiService`. Key methods:
- `getMapData()` — map endpoint
- `getEventsByRegion()` — regional events
- `getRegionalStats()` — themes/persons/orgs aggregation
- `getRiskScore(cc, startDate, endDate)` — country risk score
- `getForecast(cc)` — Prophet forecast
- `analyzeEvent(id)` — LLM analysis
- `getHealth()` / `getRuntimeSettings()` — diagnostics

---

## 8. AI/ML Components

### Event clustering (TF-IDF + KMeans)
- Input: SOURCEURL strings from hot tier, last 7 days
- Pipeline: `TfidfVectorizer(max_features=500)` → `KMeans(n_clusters=10)`
- Output: 10 semantic clusters with top terms
- Runs on-demand (cached for 1 hour per request)

### Conflict forecasting (Prophet)
- Input: daily event counts per country, filtered to QuadClass 3+4 (conflict events)
- Output: 30-day forecast with uncertainty intervals (lower_bound, upper_bound)
- Pre-computed nightly for top 50 countries via `scripts/nightly_ai.py`
- On-demand for others (slow, cached after first run)
- **Requires at least 7 days of hot-tier data** for meaningful output. With 1–2 days Prophet produces a near-flat forecast. Run `--backfill-days 7` then re-run nightly_ai.py.
- Forecast displayed in Regional Dossier as a red AreaChart with uncertainty band

### LLM briefings (Groq Llama 3 70B)
- Prompt: "Summarize the geopolitical situation in {country} based on these recent events..."
- Pre-generated nightly for top 30 countries
- On-demand fallback for others (Groq free tier: fast, <1s)

---

## 9. 5V Big Data Justification

| V | Evidence | Where to show it |
|---|---|---|
| **Volume** | GDELT Events: 3.5B+ rows, 2TB+ in BigQuery. Local hot tier: ~40 GB Parquet. | BigQuery table info screenshot + `du -sh /data/hot_tier` |
| **Velocity** | 15-min CSV fetcher: new data every 15 minutes, logged with timestamps. | systemd timer logs, last-updated timestamp in UI |
| **Variety** | Events (structured CAMEO), GKG (semi-structured themes/orgs), SOURCEURL (unstructured). | Schema screenshots of all 3 tables |
| **Veracity** | Deduplication by GLOBALEVENTID, cross-mention threshold (NumMentions ≥ 3), GoldsteinScale sanity check (-10 to +10). | Spark job output: before/after row counts |
| **Value** | Conflict forecasts, semantic clustering, LLM country briefings, geospatial map. | Live demo at URL |

### Phase 1 local evidence (Hadoop/Spark on WSL)
For the Dataset Documentation and AI Requirements reports, you need screenshots and metrics from running Spark locally:
1. Download 1 month of GDELT Events CSVs (~2 GB)
2. Store in HDFS: `hdfs dfs -put gdelt_events/ /gdelt/raw/`
3. Run Spark job: deduplicate by GLOBALEVENTID, drop nulls, cast types, write Parquet
4. Capture: Spark UI screenshot, job DAG, input/output row counts, processing time
5. These screenshots go in the Dataset Documentation report under "Tools and Technologies Used" and "5V Perspective"

---

## 10. Cost Estimation

| Component | Service | Config | Monthly USD | Monthly INR | Notes |
|---|---|---|---|---|---|
| Frontend | Vercel Hobby | Free | $0 | ₹0 | CI/CD from GitHub, global CDN |
| Backend VM compute | GCP e2-standard-2 | 2 vCPU, 8 GB, 730 hrs | $48.92 | ₹4,110 | Offset by $300 credits |
| Backend VM disk | GCP Balanced PD | 100 GB SSD | $10.00 | ₹840 | **Separate charge from compute** |
| BigQuery cold tier | BigQuery on-demand | ~30 GB scans/month | $0 | ₹0 | 3% of 1 TB free quota |
| GCS backup | GCS Standard | 5 GB, us-central1 | $0 | ₹0 | Under always-free 5 GB limit |
| AI / LLM | Groq free tier | Llama 3 70B | $0 | ₹0 | 14,400 req/day free |
| **Total** | | | **$58.92** | **₹4,960** | **Offset to ₹0 by $300 credits (~5 months)** |

**At 5,000 users:** ~₹11,560/month (~$137.69) — upgrade to e2-standard-4, 200 GB disk, add Regional Load Balancer

---

## 11. What NOT to use (and why)

| Tool | Why excluded |
|---|---|
| **Apache Kafka** | No streaming source. GDELT publishes batch CSVs, not an event stream. |
| **Apache Airflow** | Scheduler + webserver + workers consume ~2 GB RAM alone. OOMs the VM. Use cron. |
| **Apache Spark (cloud)** | Overkill for single-node 40 GB Parquet. DuckDB is faster and uses 0 extra RAM overhead. Spark is only for Phase 1 local evidence. |
| **Cloud SQL / PostgreSQL** | $30+/month for a managed DB we don't need. DuckDB handles all OLAP in-process. |
| **Redis** | Not needed. DuckDB metadata caches in memory automatically. |
| **Shared DuckDB connection + threading.Lock** | Causes all parallel dashboard queries to serialize. Use per-query fresh connections instead. |

---

## 12. GitHub Repository
 
**URL:** https://github.com/ArceusOmkar7/gdelt_global_news_trends
 
Current state (as of March 2026):
- Phase 1 (backend foundation): complete
- Phase 2 (AI analytics): complete — KMeans/TF-IDF clustering, Prophet forecasting
- Phase 3 (frontend): complete and working
  - GlobalEventMap with zoom-adaptive rendering, BBOX snapping, heatmap + event layers
  - IntelligencePanel — Event Intelligence view (QuadClass badge, Goldstein bar, CAMEO labels, actors, GKG insights, LLM analysis)
  - IntelligencePanel — Regional Dossier view (risk score, event frequency chart, conflict forecast chart, themes, entities, orgs, top events)
  - SystemControlPanel — collapsed by default, health badge always visible in header, full panel expands on click
- **UI Phase 4 — Ambient Intelligence (partially complete):**
  - ✅ 15.1 GlobalStatsTicker — fixed bottom bar, 60s refetch, collapsible
  - ✅ 15.2 TopThreatCard — sidebar card, top 5 countries by risk score, 2min refetch, collapsible
  - ⬜ 15.3 Country Choropleth Layer — not yet built
  - ⬜ 15.4 Activity Spike Alerts — not yet built
  - ⬜ 15.5 Settings Modal refactor — not yet built
- **Sidebar layout:** scrollable w-[22rem] column, pointer-events-none wrapper, header toggle to slide sidebar in/out
- **Known remaining work:** Spark/HDFS academic evidence (WSL, not blocking), GCP deployment, Nginx config, written reports
 
---

## 13. Quick reference — common tasks

**Fix BigQuery query (most urgent):**
Add `WHERE SQLDATE >= {int(yesterday.strftime('%Y%m%d'))}` and explicit column SELECT to all queries in `gdelt_repository.py`. Add `dry_run=True` cost check before executing.

**Bootstrap hot tier (first time or after VM wipe):**
```bash
python scripts/daily_bq_pull.py --backfill-days 7
python scripts/nightly_ai.py   # after backfill to get proper forecasts
```

**Set up DuckDB hot tier query (per-query connection pattern):**
```python
import duckdb
conn = duckdb.connect(database=":memory:")
try:
    result = conn.execute(
        "SELECT * FROM read_parquet('/data/hot_tier/*.parquet') WHERE ActionGeo_CountryCode = ? AND SQLDATE >= ?",
        [country_code, start_date_int]
    )
    rows = result.fetchdf()
finally:
    conn.close()
```

**Run BigQuery safely:**
```python
from google.cloud import bigquery
client = bigquery.Client()
query = """
    SELECT GLOBALEVENTID, SQLDATE, ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long,
           QuadClass, GoldsteinScale, NumMentions, AvgTone, SOURCEURL
    FROM `gdelt-bq.gdeltv2.events`
    WHERE SQLDATE >= 20250101 AND SQLDATE < 20250201
"""
job_config = bigquery.QueryJobConfig(dry_run=True)
dry = client.query(query, job_config=job_config)
assert dry.total_bytes_processed < 2_000_000_000, "Query too large!"
# Then run for real
```

**Fetch latest GDELT CSV:**
```python
import httpx, io, zipfile, pandas as pd
r = httpx.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt")
events_url = [l for l in r.text.strip().split('\n') if 'export.CSV' in l][0].split()[-1]
zdata = httpx.get(events_url).content
with zipfile.ZipFile(io.BytesIO(zdata)) as z:
    df = pd.read_csv(z.open(z.namelist()[0]), sep='\t', header=None)
```

---

## 14. Session handoff notes

### To start the next session
1. Share the latest `ingest.txt` (full codebase dump) before writing any code
2. Always read actual file contents before making edits — the summary may be out of sync

### What's working (as of March 2026)
- Full backend: FastAPI, DuckDB hot tier, BigQuery cold tier, RoutedRepository, all endpoints
- Full frontend: map, Event Intelligence panel, Regional Dossier panel, system controls
- Data pipeline: daily_bq_pull.py, realtime_fetcher.py, nightly_ai.py all written and tested
- LLM analysis: Groq + scraper working end-to-end

### What's next
1. **GCP VM deployment** — copy code to VM, set up systemd services, Nginx reverse proxy, SSL
2. **Vercel deployment** — set `VITE_API_URL` to VM's public IP, deploy frontend
3. **Spark/HDFS academic evidence** — WSL only, for Dataset Documentation report screenshots
4. **Written reports** — Cloud Cost Estimation, AI Requirements, Dataset Documentation


## 15. UI Phase 4 — Dashboard Ambient Intelligence
 
### 15.1 Global Stats Ticker ✅ COMPLETE
Fixed bottom bar (`position: fixed, bottom-0, z-50`). Fetches from
`GET /api/v1/events/global-pulse` every 60s. Shows 5 stats:
- EVENTS TODAY — total event count in date window
- MOST ACTIVE — country code + event count
- MOST HOSTILE — country with lowest avg AvgTone (min 10 events for stability)
- AVG GLOBAL TONE — mean AvgTone across all events
- CONFLICT RATIO — % of events with QuadClass 3 or 4 (red when > 35%)
 
Desktop: all items inline separated by `·`. Mobile: cycles every 3s.
Chevron toggle collapses to a 1-line strip. State in Zustand (`tickerCollapsed`).
 
**Backend endpoint:** `GET /api/v1/events/global-pulse`
- 3 DuckDB queries (global aggregates, most-active count, most-hostile country)
- 60s in-process TTL cache keyed by `{start_date}:{end_date}`
- Schemas: `GlobalPulseResponse` in `schemas.py`
- Methods: `get_global_pulse()` in `duckdb_repository.py`
 
### 15.2 Top 5 Countries by Threat Level ✅ COMPLETE
Collapsible glass-panel card in the left sidebar (below Mission Parameters).
Shows 5 rows: rank badge, country code, colored score bar (0–100), numeric score,
conflict % and event count sub-row. Clicking a row opens the Regional Dossier
(calls `setSelectedEvent(null)` then `setSelectedCountry(cc)` — ordering is mandatory).
Color: green < 30, amber 30–60, red > 60. State in Zustand (`threatCardCollapsed`).
 
**Backend endpoint:** `GET /api/v1/events/top-threat-countries?limit=5`
- Fetches top 50 countries by event volume from DuckDB
- Computes `compute_risk_score()` in Python for each, sorts descending, returns top N
- 120s in-process TTL cache keyed by `{start_date}:{end_date}:{limit}`
- Schemas: `ThreatCountryEntry`, `TopThreatCountriesResponse` in `schemas.py`
- Methods: `get_top_threat_countries()` in `duckdb_repository.py`
 
### 15.3 Country Choropleth Layer (Priority 3) ⬜ NOT YET BUILT
Color countries on the Mapbox map by risk score using a Mapbox fill layer.
Requires a static countries GeoJSON bundled in the frontend (~500 KB).
Source: https://github.com/datasets/geo-countries (public domain)
 
On load: fetch top-threat-countries endpoint (reuses 15.2 endpoint) with
limit=50 to get scores for the top 50 countries by event volume.
Build a Mapbox paint expression that maps country ISO codes to colors.
 
GDELT uses FIPS country codes, not ISO-2. Need a FIPS→ISO mapping table
(~250 entries, static JSON in frontend/src/lib/fips-to-iso.ts).
Countries with no data: transparent / very dark fill.
 
Layer sits below the heatmap and circle layers. Opacity ~0.3 so map labels
remain readable. Toggle button on the map ("CHOROPLETH ON/OFF").
 
### 15.4 Breaking: High Activity Spike Alerts (Priority 4) ⬜ NOT YET BUILT
Detect countries whose last-24h event count is ≥ 2× their 7-day rolling average.
Show pulsing alert cards overlaid on the map (absolute positioned, top-left area,
below Mission Parameters panel).
 
**New backend endpoint needed:**
GET /api/v1/events/activity-spikes
Returns: [{ country_code: str, today_count: int, baseline_avg: float, ratio: float }]
 
DuckDB query (two aggregations):
-- today
SELECT ActionGeo_CountryCode, COUNT(*) AS today_count
FROM read_parquet(...)
WHERE SQLDATE = {today_int} AND ActionGeo_CountryCode IS NOT NULL
GROUP BY ActionGeo_CountryCode
 
-- 7-day baseline
SELECT ActionGeo_CountryCode, COUNT(*) * 1.0 / 7 AS daily_avg
FROM read_parquet(...)
WHERE SQLDATE >= {seven_days_ago_int} AND SQLDATE < {today_int}
  AND ActionGeo_CountryCode IS NOT NULL
GROUP BY ActionGeo_CountryCode
 
Join in Python, filter where today_count / daily_avg >= 2.0, sort by ratio desc,
return top 5 spikes. Cache 5 minutes.
 
Frontend: each alert is a small pulsing card with cyber-red border.
Shows: "⚠ {CC} — {ratio:.1f}× normal activity"
Clicking opens Regional Dossier for that country.
Entire alert stack is collapsible. refetchInterval: 5min.
 
### 15.5 UI Refactor — Settings Modal (All Priorities) ⬜ NOT YET BUILT
The SystemControlPanel (Runtime Controls + System Health + Backend Runtime Settings)
should move into a Settings modal triggered by a gear icon button in the header.
The left sidebar should only contain: Mission Parameters, Top Threat Countries card,
and the Spike Alerts stack.
 
Settings modal contents (same data, new location):
- Map Auto-Refresh toggle + fetch interval
- Health polling interval
- System Health status
- Backend Runtime Settings (all the BQ cap / cron / cutoff numbers)
 
The modal uses the same glass-panel / font-mono aesthetic.
A single ⚙ SETTINGS button in the header (top-right area) opens it.
