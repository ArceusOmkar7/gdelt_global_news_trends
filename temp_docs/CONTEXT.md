# GNIEM — Project Context & Architecture Reference

> **For AI assistants:** This file is the single source of truth for the GNIEM project. Read it fully before generating any code, queries, configs, or documentation. Do not assume anything not stated here.

---

## Session Findings & Roadmap (March 20, 2026)

### Status Update
- **Data Enrichment**: Hot-tier Parquet schema updated. Now includes `themes`, `persons`, `organizations`, `mentions_count`, and `avg_confidence`.
- **Map Visualization**:
    - Fixed "artificial grid" by increasing `grid_precision` dynamically.
    - Fixed "missing points" at high zoom by delaying detailed transition to level 12 and using high-precision bins (~1m) for aggregated centroids.
- **Map Stability Hardening**:
    - Frontend map requests now pass abort signals so superseded viewport requests are cancelled.
    - BBOX refresh now occurs on map move-end to reduce transient viewport churn.
    - Detail click path now includes fallback event selection from clicked feature properties.
    - Frontend query cache uses zoom-adaptive BBOX snapping and 2-minute staleTime to reduce backend hits.
    - Backend `map.py` now has an in-process TTL response cache (60s agg, 120s detail).
    - `get_event_details` now accepts `min_mentions` parameter — zoom-scaled filtering reduces DuckDB scan work and payload size at detail zoom.
- **Backend Concurrency Hardening**:
    - DuckDB repository serializes all shared-connection calls with a lock.
    - `/health` BigQuery connectivity probe cached for 60 seconds.
- **Daily Ingestion Improvements**:
    - `scripts/daily_bq_pull.py` now joins Events + Mentions + GKG using URL-filtered GKG fetch (matching only known SOURCEURLs and mention URLs), reducing GKG scan from 500MB to ~50MB.
    - GKG match rate improved from ~8% (SOURCEURL-only join) to ~50-70% (via Mentions.MentionIdentifier bridge).
    - Added `--date YYYY-MM-DD` and `--backfill-days N` (max 7) CLI arguments.
- **System Stability**: Frontend build restored; backend multi-query ingestion implemented.

### Current Known Issues
1. **LLM Analysis endpoint (`/events/{id}/analyze`) is returning "ANALYSIS FAILED"** — the `llm_analysis_service.py` or `scraper_service.py` is broken. Needs investigation. This is visible in the UI as "FAILED TO FETCH" under the Analysis section.
2. **GKG match rate is ~50-70%** — events with no matching GKG article will have empty `themes`, `persons`, `organizations`. Frontend already handles this gracefully but it means enrichment is not universal.

### Pending Tasks — Next Priority Order
1. **Fix LLM analysis endpoint** — investigate `llm_analysis_service.py` and `scraper_service.py`, confirm Groq API key is set and working.
2. **Surface unused columns** — `QuadClass`, `Actor1Type1Code`, `Actor2Type1Code`, `EventCode` are stored in Parquet but never returned to the frontend. See Section 17 for full plan.
3. **Intelligence panel redesign** — replace raw codes with human-readable labels, add country risk score, add event timeline chart. See Section 17.
4. **Conflict forecasting panel** — Prophet forecasts are precomputed nightly but no frontend UI consumes them yet.
5. **Spark/HDFS evidence** — still pending for Big Data report. See Section 9.

---

## Change Log (March 2026)

- **BigQuery safety hardening completed**
- **Scan budget enforcement implemented**
- **Hot-tier repository added**
- **Settings and startup robustness improved**
- **Hot/cold routing and cold-tier policy enforcement completed**
- **Backend verification expanded — 55 tests passing**
- **Priority 1 ingestion scripts completed**
- **Frontend runtime controls added**
- **BigQuery partition pruning correction completed**
- **Map data rendering and aggregation stability fixes completed**
- **Frontend map readability and drill-down interaction improved**
- **LLM model defaults updated**
- **Map rendering and interaction stability fixes**
- **Frontend build and TypeScript configuration restored**
- **Geopolitical intelligence enriched with GKG and Mentions**
- **Map query lifecycle and backend stability hardening completed**
- **Daily ingestion script enhancements completed**
    - URL-filtered GKG fetch via Mentions bridge
    - CLI backfill options added (`--date`, `--backfill-days`)
- **Map performance hardening completed**
    - Frontend BBOX snapping (zoom-adaptive grid), staleTime 2min, gcTime 10min
    - Backend in-process TTL cache in `map.py`
    - `min_mentions` zoom-scaled filter threaded through all layers: `map.py` → `get_events.py` → `routed_repository.py` → `duckdb_repository.py`

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
| **Mentions** | Each article that mentions each event. Confidence scores, article URLs. | BigQuery public dataset |

### BigQuery identifiers (CRITICAL — these are the correct table refs)
```
gdelt-bq.gdeltv2.events                     -- legacy non-partitioned table
gdelt-bq.gdeltv2.events_partitioned         -- DAY-partitioned (recommended)
gdelt-bq.gdeltv2.gkg                        -- legacy non-partitioned table
gdelt-bq.gdeltv2.gkg_partitioned            -- DAY-partitioned
gdelt-bq.gdeltv2.eventmentions              -- legacy non-partitioned table
gdelt-bq.gdeltv2.eventmentions_partitioned  -- DAY-partitioned
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
**Do NOT select:** Actor1Name, Actor2Name, Actor1Geo_FullName, Actor2Geo_FullName, MentionDocLen, or any column not in the list above, unless explicitly required.

### BigQuery query safety rules (MANDATORY)
1. **Always filter by SQLDATE** using integer comparison: `WHERE SQLDATE >= 20250101`
2. **Never use `BETWEEN` on SQLDATE** — use `>=` and `<` with integer literals
3. **Never `SELECT *`** — always explicit column list
4. **Wrap all BigQuery calls with cost estimation** using `dry_run=True` before executing
5. **Daily batch job max scan budget:** 2 GB per run (hard limit in code)
6. **Fallback queries only:** BigQuery is only queried for dates older than 90 days. All recent data comes from local Parquet.

### BigQuery scan cost analysis

| Table | Full table size | Full scan (no guards) | After col pruning + 1-day partition | Monthly (30 daily runs) |
|---|---|---|---|---|
| Events | ~63 GB | ~6 GB | **~45 MB/day** | ~1.35 GB |
| EventMentions | ~104 GB | ~10 GB | **~8 MB/day** | ~240 MB |
| GKG | ~3.6 TB | ~7.7 GB | **~459 MB/day** (URL-filtered) | ~14 GB |
| **All 3 combined** | | | | **~15.6 GB/month = ~1.6% of free quota** |

**GKG is uniquely dangerous.** Without the DATE partition filter, one GKG query scans the full 3.6 TB table = ~$17.50 instantly.

**Cold tier scan costs (Events only):**

| Date range requested | Events scan per query | Safe? |
|---|---|---|
| 7 days | ~50–100 MB | ✓ Very safe |
| 30 days | ~200–450 MB | ✓ Yes |
| 90 days | ~600 MB–1.5 GB | ✓ Yes |
| All history (no filter!) | ~63 GB | ✗ Never |

### 15-minute CSV feed (near-realtime — free, no BigQuery)
```
http://data.gdeltproject.org/gdeltv2/lastupdate.txt
```

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
- **GKG is NEVER queried through the cold tier** — GKG only accessed during daily hot tier batch job

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

**Not running on VM:** Airflow, Kafka, Spark, Redis, PostgreSQL.

### Scaling strategy
**Current (100 users):** Single VM, no load balancer, Nginx handles all traffic directly.
**At 5,000 users:** Manual scaling — upgrade VM to e2-standard-4, expand disk to 200 GB, add GCP Regional External Load Balancer. This is deliberate manual scaling, not auto-scaling or containerization.

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
- Pulls one day at a time using partition-pruned queries against Events, EventMentions, and GKG
- **Join strategy:** Events → Mentions (for `mentions_count`, `avg_confidence`, and `mention_urls`) → GKG (URL-filtered using both SOURCEURL and Mentions.MentionIdentifier as candidates)
- GKG match rate: ~50–70% of events get themes/persons/organizations enrichment
- Supports CLI modes:
    - `python scripts/daily_bq_pull.py` (default: yesterday)
    - `python scripts/daily_bq_pull.py --date YYYY-MM-DD` (single date, max 7 days back)
    - `python scripts/daily_bq_pull.py --backfill-days N` (up to 7 days, oldest first)
- Appends to `/data/hot_tier/events_YYYYMM.parquet` (one file per month)
- Hard limit: abort if estimated bytes > 2 GB

### 15-minute CSV fetcher (`scripts/realtime_fetcher.py`)
- Runs every 15 min via systemd timer
- Fetches `lastupdate.txt`, parses the Events CSV URL
- Deduplicates by GLOBALEVENTID against last 1000 rows of hot tier
- Appends to `/data/hot_tier/realtime_buffer.parquet`

### Nightly AI jobs (`scripts/nightly_ai.py`)
- **Prophet forecasting:** Top 50 countries, 30-day forecast. Output: `/data/cache/forecasts.parquet`
- **Groq briefings:** Top 30 countries, last 7 days. Output: `/data/cache/briefings.json`
- Runs at 3am UTC (after batch pull completes)

### Cold tier rules (MANDATORY — do not relax these)
1. **Events table only** — never query GKG or EventMentions through the cold tier.
2. **Maximum 30-day date window per cold query**
3. **Maximum 3 cold queries per user per month**
4. **Always use `dry_run=True`** before executing any cold query. Abort if estimated bytes > 2 GB.
5. **Cache cold results** — keyed by request shape hash, stored as Parquet.
6. **Cold results are Events-only** — no GKG enrichment on cold tier data.

---

## 6. Backend Structure (FastAPI + Clean Architecture)

```
backend/
├── api/
│   ├── main.py               # FastAPI app, lifespan, CORS, middleware
│   ├── request_context.py    # Request-scoped user identity for quota accounting
│   ├── routers/
│   │   ├── events.py         # GET /events, /events/region/{cc}, /events/counts
│   │   ├── analytics.py      # GET /analytics/clusters, /analytics/forecast
│   │   ├── map.py            # GET /events/map — zoom-aware, TTL-cached, min_mentions filter
│   │   └── health.py         # GET /health, /health/settings
│   └── schemas/
│       └── schemas.py        # Pydantic response models
├── application/
│   └── use_cases/
│       ├── get_events.py     # get_map_event_details now accepts min_mentions
│       ├── cluster_events.py
│       ├── forecast_events.py
│       └── analyze_event.py
├── domain/
│   ├── models/
│   │   └── event.py
│   └── ports/
│       └── ports.py
└── infrastructure/
    ├── config/
    │   └── settings.py
    ├── data_access/
    │   ├── bigquery_client.py
    │   ├── gdelt_repository.py
    │   ├── duckdb_repository.py  # get_event_details now accepts min_mentions
    │   └── routed_repository.py  # get_event_details now accepts min_mentions
    └── services/
        ├── llm_analysis_service.py  # ⚠️ BROKEN — analyze endpoint failing
        └── scraper_service.py       # ⚠️ BROKEN — needs investigation
```

### Environment variables (`.env`)
```
GCP_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GDELT_DATASET=gdelt-bq.gdeltv2
HOT_TIER_PATH=/data/hot_tier
CACHE_PATH=/data/cache
HOT_TIER_CUTOFF_DAYS=90
COLD_TIER_MAX_WINDOW_DAYS=30
COLD_TIER_MONTHLY_QUERY_LIMIT=3
GROQ_API_KEY=
MAPBOX_TOKEN=
ENVIRONMENT=production
BQ_MAX_SCAN_BYTES=2000000000
```

---

## 7. Frontend Structure (React + Vite)

```
frontend/src/
├── App.tsx
├── components/
│   ├── map/
│   │   └── GlobalEventMap.tsx   # Mapbox map, zoom-adaptive BBOX snapping, TTL cache
│   └── tables/
│       ├── IntelligencePanel.tsx # Event + regional dossier panel (⚠️ analysis broken)
│       └── SystemControlPanel.tsx
├── services/
│   └── api.ts                   # Typed API client with AbortSignal support
├── store/
│   └── useStore.ts
└── types/
    └── index.ts
```

### Map behavior
- **Zoom < 9:** Aggregated heatmap + intensity circles. Click drills down to zoom 9.2.
- **Zoom ≥ 9:** Individual event circles. `min_mentions` filter scales with zoom (zoom 9 → min 3, zoom 11+ → min 1).
- **BBOX snapping:** zoom < 4 → 5° grid, zoom 4–8 → 1° grid, zoom 8–11 → 0.2° grid, zoom 11+ → 0.05° grid.
- **Cache:** React Query staleTime 2min, gcTime 10min. Backend TTL cache 60s (agg) / 120s (detail).

---

## 8. AI/ML Components

### Event clustering (TF-IDF + KMeans)
- Input: SOURCEURL strings from hot tier, last 7 days
- Pipeline: `TfidfVectorizer(max_features=500)` → `KMeans(n_clusters=10)`
- Output: 10 semantic clusters with top terms
- Runs on-demand (cached 1 hour)

### Conflict forecasting (Prophet)
- Input: daily event counts per country, QuadClass 3+4 only
- Output: 30-day forecast with uncertainty intervals
- Pre-computed nightly for top 50 countries
- **⚠️ Frontend UI for forecasting not yet built** — data exists in `/data/cache/forecasts.parquet` but nothing renders it

### LLM briefings (Groq Llama 3 70B / llama-3.1-8b-instant)
- Pre-generated nightly for top 30 countries
- On-demand fallback for others
- **⚠️ On-demand analyze endpoint currently broken** — see Section 6

---

## 9. 5V Big Data Justification

| V | Evidence | Where to show it |
|---|---|---|
| **Volume** | GDELT Events: 3.5B+ rows, 2TB+ in BigQuery. Local hot tier: ~40 GB Parquet. | BigQuery table info screenshot + `du -sh /data/hot_tier` |
| **Velocity** | 15-min CSV fetcher: new data every 15 minutes, logged with timestamps. | systemd timer logs, last-updated timestamp in UI |
| **Variety** | Events (structured CAMEO), GKG (semi-structured themes/orgs), SOURCEURL (unstructured). | Schema screenshots of all 3 tables |
| **Veracity** | Deduplication by GLOBALEVENTID, NumMentions threshold, GoldsteinScale sanity check. | Spark job output: before/after row counts |
| **Value** | Conflict forecasts, semantic clustering, LLM country briefings, geospatial map. | Live demo at URL |

### Spark/HDFS local evidence (STILL PENDING — needed for reports)
1. Download 1 month of GDELT Events CSVs (~2 GB)
2. Store in HDFS: `hdfs dfs -put gdelt_events/ /gdelt/raw/`
3. Run Spark job: deduplicate by GLOBALEVENTID, drop nulls, cast types, write Parquet
4. Capture: Spark UI screenshot, job DAG, input/output row counts, processing time
5. Screenshots go in Dataset Documentation report under "Tools and Technologies Used"

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

**At 5,000 users:** ~₹11,560/month (~$137.69) — e2-standard-4, 200 GB disk, Regional Load Balancer

---

## 11. What NOT to use (and why)

| Tool | Why excluded |
|---|---|
| **Apache Kafka** | No streaming source. GDELT publishes batch CSVs, not an event stream. |
| **Apache Airflow** | Scheduler + webserver + workers consume ~2 GB RAM alone. OOMs the VM. Use cron. |
| **Apache Spark (cloud)** | Overkill for single-node 40 GB Parquet. DuckDB is faster. Spark is only for Phase 1 local evidence. |
| **Cloud SQL / PostgreSQL** | $30+/month for a managed DB we don't need. DuckDB handles all OLAP in-process. |
| **Redis** | Not needed. DuckDB metadata caches in memory automatically. |

---

## 12. GitHub Repository

**URL:** https://github.com/ArceusOmkar7/gdelt_global_news_trends

---

## 13. Quick reference — common tasks

**Run DuckDB hot tier query:**
```python
import duckdb
conn = duckdb.connect()
result = conn.execute(
    "SELECT * FROM read_parquet('/data/hot_tier/*.parquet') WHERE ActionGeo_CountryCode = ? AND SQLDATE >= ?",
    [country_code, start_date_int]
).fetchdf()
```

**Run BigQuery safely:**
```python
from google.cloud import bigquery
client = bigquery.Client()
query = """
    SELECT GLOBALEVENTID, SQLDATE, ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long,
           QuadClass, GoldsteinScale, NumMentions, AvgTone, SOURCEURL
    FROM `gdelt-bq.gdeltv2.events_partitioned`
    WHERE _PARTITIONDATE = '2026-03-19' AND SQLDATE = 20260319
"""
job_config = bigquery.QueryJobConfig(dry_run=True)
dry = client.query(query, job_config=job_config)
assert dry.total_bytes_processed < 2_000_000_000, "Query too large!"
```

**Backfill hot tier:**
```bash
PYTHONPATH=. python scripts/daily_bq_pull.py --backfill-days 7
```

---

## 14. Current File Status

| File | Status | Notes |
|---|---|---|
| `backend/infrastructure/data_access/gdelt_repository.py` | 🟢 FIXED | Partition filters, column pruning |
| `backend/infrastructure/data_access/bigquery_client.py` | 🟢 FIXED | dry_run guard + scan budget |
| `backend/infrastructure/data_access/duckdb_repository.py` | 🟢 UPDATED | `get_event_details` accepts `min_mentions` |
| `backend/infrastructure/data_access/routed_repository.py` | 🟢 UPDATED | `get_event_details` accepts `min_mentions`, passes through all route paths |
| `backend/application/use_cases/get_events.py` | 🟢 UPDATED | `get_map_event_details` accepts and passes `min_mentions` |
| `backend/api/routers/map.py` | 🟢 UPDATED | In-process TTL cache, zoom-scaled `min_mentions` and `detail_limit` |
| `backend/api/request_context.py` | 🟢 ADDED | Request-scoped user identity |
| `backend/infrastructure/config/settings.py` | 🟢 UPDATED | Runtime tier settings |
| `backend/api/main.py` | 🟢 UPDATED | Routed repository + middleware + cold policy handler |
| `backend/api/routers/events.py` | 🟢 ROUTED | No direct BigQuery dependency |
| `backend/api/routers/analytics.py` | 🟢 ROUTED | Via routed repository |
| `backend/api/routers/health.py` | 🟢 UPDATED | Hot-tier diagnostics + settings endpoint |
| `backend/infrastructure/services/llm_analysis_service.py` | 🔴 BROKEN | Analyze endpoint returning 500 |
| `backend/infrastructure/services/scraper_service.py` | 🔴 BROKEN | Needs investigation |
| `scripts/daily_bq_pull.py` | 🟢 UPDATED | Events+Mentions+GKG join, URL-filtered GKG, CLI args |
| `scripts/realtime_fetcher.py` | 🟢 ADDED | 15-min CSV ingestion |
| `scripts/nightly_ai.py` | 🟢 UPDATED | Forecasts + briefings precompute |
| `frontend/src/components/map/GlobalEventMap.tsx` | 🟢 UPDATED | BBOX snapping, staleTime 2min, gcTime 10min |
| `frontend/src/` | 🟢 BUILDS | TypeScript config restored |

---

## 15. Known Edge Cases

1. **Per-user cold quota identity is coarse** — IP fallback means users behind NAT share quota.
2. **Cold query counter is file-based and process-local** — not safe across multiple Uvicorn workers.
3. **Cold cache has no TTL/LRU cleanup** — files grow over time.
4. **GKG match rate is ~50-70%** — events with no GKG match have empty themes/persons/organizations.
5. **Parquet hot tier only has data for days the script was actually run** — not automatically backfilled. Run `--backfill-days 7` manually after first deployment.

---

## 16. What Next (Execution Order)

### Priority 1 — Fix broken analyze endpoint
- Investigate `llm_analysis_service.py` and `scraper_service.py`
- Confirm `GROQ_API_KEY` is set in `.env`
- Check what the actual 500 error is in the backend logs

### Priority 2 — Surface unused data (see Section 17 for full plan)
- Add `QuadClass`, `Actor1Type1Code`, `Actor2Type1Code`, `EventCode` to `MapEventDetail` domain model and API schema
- Add these to `_row_to_map_detail` in `duckdb_repository.py`
- Add these to the `SELECT` list in `get_event_details` SQL query
- Update `MapEventDetailResponse` schema in `schemas.py`
- Update `Event` and `MapEventDetail` types in `frontend/src/types/index.ts`

### Priority 3 — Intelligence panel redesign (see Section 17)
- CAMEO code → human-readable label lookup
- QuadClass → color + label (Verbal Cooperation / Material Cooperation / Verbal Conflict / Material Conflict)
- Country risk score card (DuckDB aggregation)
- Event timeline chart (Recharts, uses existing `/events/counts/{cc}` endpoint)
- Conflict forecasting panel (uses existing `/analytics/forecast/{cc}` endpoint)

### Priority 4 — Ops and deployment hygiene
- Add systemd unit + timer files for 15-minute fetcher
- Add cron examples for daily and nightly jobs
- Add cache cleanup job for `CACHE_PATH/cold_queries`

### Priority 5 — Spark/HDFS academic evidence
- Run on WSL, capture screenshots and job DAGs for Big Data report

---

## 17. Unused Data & Intelligence Panel Redesign Plan

This section documents exactly what data is available but not yet used, and the full plan to surface it. **This is the primary feature work for the next session.**

### 17.1 Columns stored in Parquet but not returned to frontend

| Column | Currently used | Value if surfaced |
|---|---|---|
| `QuadClass` | ✗ stored, never returned | Most important — 1=Verbal Coop, 2=Material Coop, 3=Verbal Conflict, 4=Material Conflict. Use for map dot color and risk score. |
| `Actor1Type1Code` | ✗ stored, never returned | Actor type: GOV, MIL, REB, CVL, etc. Needed for bilateral tension tracker and actor breakdown. |
| `Actor2Type1Code` | ✗ stored, never returned | Same as above for Actor 2. |
| `EventCode` | ✓ stored, returned in `get_events` only | More specific than EventRootCode. "141" = demonstrate vs "145" = hunger strike. |
| `EventBaseCode` | ✗ stored, never returned | Mid-level CAMEO code. Useful for grouping. |
| `Actor1Geo_CountryCode` | ✗ stored, never returned | Where Actor 1 is from. Different from ActionGeo (where event happened). Needed for bilateral tracker. |
| `Actor2Geo_CountryCode` | ✗ stored, never returned | Same for Actor 2. |
| `MonthYear` | ✗ stored, never used | Not needed — derivable from SQLDATE. |
| `Year` | ✗ stored, never used | Not needed — derivable from SQLDATE. |
| `avg_confidence` | ✓ stored, returned, but not displayed in frontend | Show in media reach section. |
| `mentions_count` | ✓ stored, returned, but not displayed in frontend | Show in media reach section. |

### 17.2 Backend changes needed to surface unused columns

**Step 1 — Add to domain model** (`backend/domain/models/event.py`):
Add `quad_class`, `actor1_type_code`, `actor2_type_code`, `event_code` to `MapEventDetail`.

**Step 2 — Add to DuckDB SELECT** (`backend/infrastructure/data_access/duckdb_repository.py`):
In `get_event_details` SQL, add to the SELECT list:
```sql
QuadClass,
Actor1Type1Code AS actor1_type_code,
Actor2Type1Code AS actor2_type_code,
EventCode,
Actor1Geo_CountryCode,
Actor2Geo_CountryCode,
```

**Step 3 — Add to `_row_to_map_detail`** in the same file:
```python
quad_class=row.get("QuadClass"),
actor1_type_code=row.get("actor1_type_code"),
actor2_type_code=row.get("actor2_type_code"),
event_code=row.get("EventCode"),
actor1_geo_country_code=row.get("Actor1Geo_CountryCode"),
actor2_geo_country_code=row.get("Actor2Geo_CountryCode"),
```

**Step 4 — Add to API schema** (`backend/api/schemas/schemas.py`):
Add same fields to `MapEventDetailResponse`.

**Step 5 — Add to frontend types** (`frontend/src/types/index.ts`):
Add same fields to the `Event` interface.

### 17.3 CAMEO and QuadClass lookup tables (for frontend display)

These are static lookup tables the frontend should embed — no API call needed.

**QuadClass lookup:**
```ts
const QUAD_CLASS_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'Verbal Cooperation',  color: '#00f3ff' },  // teal
  2: { label: 'Material Cooperation', color: '#00ff41' }, // green
  3: { label: 'Verbal Conflict',      color: '#ffdc00' }, // amber
  4: { label: 'Material Conflict',    color: '#ff003c' }, // red
};
```

**CAMEO EventRootCode lookup (top 20 most common):**
```ts
const CAMEO_ROOT_LABELS: Record<string, string> = {
  '01': 'Make Public Statement',
  '02': 'Appeal',
  '03': 'Express Intent to Cooperate',
  '04': 'Consult',
  '05': 'Engage in Diplomatic Cooperation',
  '06': 'Engage in Material Cooperation',
  '07': 'Provide Aid',
  '08': 'Yield',
  '09': 'Investigate',
  '10': 'Demand',
  '11': 'Disapprove',
  '12': 'Reject',
  '13': 'Threaten',
  '14': 'Protest',
  '15': 'Exhibit Military Posture',
  '16': 'Reduce Relations',
  '17': 'Coerce',
  '18': 'Assault',
  '19': 'Fight',
  '20': 'Use Unconventional Mass Violence',
};
```

**Actor type code lookup:**
```ts
const ACTOR_TYPE_LABELS: Record<string, string> = {
  'GOV': 'Government',
  'MIL': 'Military',
  'REB': 'Rebel',
  'MED': 'Media',
  'NGO': 'NGO',
  'IGO': 'Intergovernmental Org',
  'CVL': 'Civilian',
  'OPP': 'Political Opposition',
  'BUS': 'Business',
  'CRM': 'Criminal',
  'UAF': 'Unaffiliated Armed Forces',
  'AGR': 'Agriculture',
  'EDU': 'Education',
  'ELI': 'Elite',
  'ENV': 'Environment',
  'HLH': 'Health',
  'LAB': 'Labor',
  'LEG': 'Legislature',
  'REL': 'Religion',
  'SOC': 'Social',
  'SPY': 'Intelligence',
  'JUD': 'Judiciary',
  'MOD': 'Moderate',
  'RAD': 'Radical',
  'REF': 'Refugee',
  'SET': 'Settler',
  'VET': 'Veteran',
};
```

### 17.4 Intelligence Panel redesign — what to build

**Current state (what the panel shows):**
- Raw numbers: Goldstein -2.0, Tone -2.5, Mentions 1, Sources 1
- Raw code: CAMEO Root Code "09"
- Raw code: Actor 1 "IND"
- Raw GKG theme codes: `WB_696_PUBLIC_SECTOR_MANAGEMENT`, `EPU_POLICY_REGULATORY`

**Problem:** Raw codes, no narrative, no context for what numbers mean, no country-level summary.

**Target state — Event Intelligence panel should show:**

1. **QuadClass badge** — large colored badge: "MATERIAL CONFLICT" in red or "VERBAL COOPERATION" in teal. This is the first thing a user should see.

2. **CAMEO label** — instead of "09", show "Investigate" with the code in smaller text below.

3. **Actor display** — instead of "IND", show the country flag emoji + full name + actor type label. E.g. "🇮🇳 India — Government" using the `Actor1Type1Code` lookup.

4. **Goldstein context** — add a mini progress bar from -10 to +10 with the value marked. Add a label: "Moderately Destabilizing" for -2.0 to -5.0 range.

5. **GKG themes** — strip the `WB_`, `EPU_`, `SOC_` prefixes and convert underscores to spaces. `WB_696_PUBLIC_SECTOR_MANAGEMENT` → "Public Sector Management". Show top 5 only.

6. **Media reach** — show `mentions_count` and `avg_confidence` as a media reach indicator, not just raw numbers.

**Target state — Regional Dossier panel should show:**

1. **Country risk score card** — a 0–100 score derived from a DuckDB aggregation over the selected date range:
   - Formula: `score = (conflict_ratio * 40) + (avg_goldstein_normalized * 30) + (avg_tone_normalized * 20) + (media_spike * 10)`
   - This requires a new backend endpoint: `GET /events/region/{cc}/risk-score?start_date=&end_date=`
   - Color: green < 30, amber 30–60, red > 60

2. **Event timeline chart** — daily event count line chart using Recharts. Data from existing `/events/counts/{cc}` endpoint. Show last 14 days. Color conflict events (QuadClass 3+4) separately from cooperation (1+2).

3. **Actor breakdown** — pie or bar chart: what % of events involve MIL vs GOV vs REB actors. Uses `Actor1Type1Code` from the new enriched detail endpoint.

4. **Top event types** — horizontal bar chart of top 5 CAMEO root codes with human-readable labels.

5. **Conflict forecast** — line chart using existing `/analytics/forecast/{cc}` endpoint. Show next 30 days with uncertainty band. **Data already exists, just needs a UI.**

### 17.5 New backend endpoint needed: Country Risk Score

This is a single DuckDB aggregation query — not a BigQuery query.

```
GET /api/v1/events/region/{country_code}/risk-score
Query params: start_date, end_date
Returns: { score: float, trend: "improving"|"stable"|"worsening", conflict_ratio: float, avg_goldstein: float, avg_tone: float, total_events: int }
```

DuckDB query:
```sql
SELECT
    COUNT(*) AS total_events,
    SUM(CASE WHEN QuadClass IN (3, 4) THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS conflict_ratio,
    AVG(GoldsteinScale) AS avg_goldstein,
    AVG(AvgTone) AS avg_tone,
    SUM(NumMentions) AS total_mentions
FROM read_parquet('/data/hot_tier/*.parquet')
WHERE ActionGeo_CountryCode = ?
  AND SQLDATE >= ?
  AND SQLDATE < ?
```

Score formula (0–100, higher = more dangerous):
```python
def compute_risk_score(conflict_ratio, avg_goldstein, avg_tone):
    # conflict_ratio: 0.0–1.0, higher = more conflict
    # avg_goldstein: -10 to +10, more negative = more conflict
    # avg_tone: typically -30 to +30, more negative = more hostile
    goldstein_score = max(0, min(100, ((-avg_goldstein + 10) / 20) * 100))
    tone_score = max(0, min(100, ((-avg_tone + 30) / 60) * 100))
    conflict_score = conflict_ratio * 100
    return round(conflict_score * 0.4 + goldstein_score * 0.35 + tone_score * 0.25)
```

---

## 18. GKG Theme Code Cleanup (for frontend display)

GKG theme codes look like `WB_696_PUBLIC_SECTOR_MANAGEMENT` or `EPU_POLICY_REGULATORY` or `SOC_GENERALCRIME`. These are machine-readable codes, not human labels.

**Cleanup function for frontend:**
```ts
function cleanGkgTheme(raw: string): string {
  // Remove known prefixes
  const prefixes = ['WB_\\d+_', 'EPU_', 'SOC_', 'ENV_', 'ECON_', 'MED_', 'TAX_'];
  let clean = raw;
  for (const prefix of prefixes) {
    clean = clean.replace(new RegExp(`^${prefix}`), '');
  }
  // Convert underscores to spaces, title case
  return clean
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase());
}

// Example:
// WB_696_PUBLIC_SECTOR_MANAGEMENT → "Public Sector Management"
// EPU_POLICY_REGULATORY → "Policy Regulatory"
// TAX_WEAPONS_BOMB → "Weapons Bomb"
// SOC_GENERALCRIME → "Generalcrime"  (not perfect but readable)
```

Apply this in `IntelligencePanel.tsx` when rendering the themes list.

