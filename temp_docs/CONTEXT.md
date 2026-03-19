# GNIEM — Project Context & Architecture Reference

> **For AI assistants:** This file is the single source of truth for the GNIEM project. Read it fully before generating any code, queries, configs, or documentation. Do not assume anything not stated here.

## Change Log (March 2026)

- **BigQuery safety hardening completed**
    - `backend/infrastructure/data_access/gdelt_repository.py` now uses SQLDATE partition filters with `>=` and `<`.
    - Repository queries now use explicit column projection (no `SELECT *`).
    - Events/counted article metrics not in approved projection were removed from response/domain models (`num_articles`, `total_articles`).
- **Scan budget enforcement implemented**
    - `backend/infrastructure/data_access/bigquery_client.py` now runs `dry_run=True` before execution and rejects queries over `BQ_MAX_SCAN_BYTES`.
- **Hot-tier repository added**
    - `backend/infrastructure/data_access/duckdb_repository.py` created and implements `IEventRepository` against local Parquet.
    - Hard-failure behavior enforced when `HOT_TIER_PATH` is missing or contains no parquet files.
- **Settings and startup robustness improved**
    - `backend/infrastructure/config/settings.py` now includes `HOT_TIER_PATH` and `BQ_MAX_SCAN_BYTES`.
    - Backend settings now ignore unrelated `.env` variables (for shared frontend/backend env files).
    - Forecasting service lazy-loads Prophet/Pandas during forecast execution to reduce API startup latency.
- **Environment migration**
    - Active project has been copied to WSL-native path for faster dev workflows: `/home/sasuke/projects/gdelt_global_news_trends`.
- **Hot/cold routing and cold-tier policy enforcement completed**
    - Added `backend/infrastructure/data_access/routed_repository.py` to route requests across DuckDB hot tier and BigQuery cold tier using a shared 90-day cutoff.
    - Implemented cold-tier guardrails in the routed repository: max 30-day window, max 3 cold queries per user per month, and parquet cache for repeated cold requests.
    - Added request-scoped user identity context via `backend/api/request_context.py` and middleware in `backend/api/main.py` (`x-user-id` -> `x-forwarded-for` -> client IP fallback).
    - Added `ColdTierPolicyError` handling in FastAPI with clear `400/429` responses.
    - Health endpoint now reports hot-tier availability and parquet file count alongside BigQuery status.
- **Backend verification expanded**
    - Added `backend/tests/unit/test_routed_repository.py` covering hot/cold/hybrid routing, cold window limit, monthly quota, and cache reuse.
    - Updated map integration test threshold to align with router behavior (`zoom >= 9` => detailed view).
    - Backend unit + integration suite currently passes: **55 passed**.
- **Priority 1 ingestion scripts completed**
    - Added `scripts/daily_bq_pull.py` with SQLDATE partition pull (`>=` / `<`), explicit Events projection, and dry-run guarded BigQuery execution.
    - Added `scripts/realtime_fetcher.py` for 15-minute Events CSV ingestion with approved column projection and `GLOBALEVENTID` deduplication.
    - Added `scripts/nightly_ai.py` to precompute `forecasts.parquet` and `briefings.json` under `CACHE_PATH`.
    - Added script-focused unit tests for query guardrails and ingestion edge cases.
- **Frontend runtime controls added**
    - Added UI controls to change map fetch interval and health polling interval at runtime.
    - Added live health status card in frontend using `/health` endpoint (BigQuery + hot-tier diagnostics).
    - Added backend runtime settings endpoint `/health/settings` and frontend panel bindings for operational visibility (cutoffs, cold-tier limits, scan cap, and ingestion cadences).
- **BigQuery partition pruning correction completed**
    - Confirmed `gdelt-bq.gdeltv2.events` is not partitioned and would trigger high dry-run estimates.
    - Updated backend/query paths to target partitioned table variants (for example `events_partitioned`) and enforce `_PARTITIONDATE` pruning with SQLDATE bounds.
    - Daily ingestion now scans within budget again and successfully writes real hot-tier parquet.
- **Map data rendering and aggregation stability fixes completed**
    - Fixed DuckDB map aggregation placeholder ordering bug that caused empty map results despite available data.
    - Added `backend/tests/unit/test_duckdb_repository.py` regression coverage for map aggregation.
    - Replaced frontend Deck.GL map-layer rendering path with native Mapbox GeoJSON layers to avoid luma.gl shader compile/link failures on affected GPU/driver stacks.
- **Frontend map readability and drill-down interaction improved**
    - Aggregated map view now uses a zoom-adaptive hybrid of heatmap + intensity circles for better readability across global-to-regional scales.
    - Detailed event circles now use lower opacity scaling to preserve basemap context.
    - Added aggregate-circle click drill-down in `frontend/src/components/map/GlobalEventMap.tsx` to recenter and jump directly to detailed mode (`zoom >= 9`) for per-event inspection.
    - Restored reliable aggregate interaction at low zoom by keeping aggregate circles interactive and visible while heatmap fades by zoom.
- **LLM model defaults updated**
    - Backend LLM default model changed to `gemini-2.5-flash` in settings and `.env.example`.
    - Nightly Groq briefing model changed to `llama-3.1-8b-instant` for faster low-cost summarization.
- **Map rendering and interaction stability fixes**
    - Fixed DuckDB repository BBOX filtering to handle International Date Line (antimeridian) crossing and full-world views (>= 360 degrees).
    - Improved map responsiveness by reducing BBOX update debounce to 100ms.
    - Enhanced visual clarity by extending heatmap visibility to zoom level 7 and increasing point radius/opacity.
    - Hardened map interaction by allowing concurrent clicks on both aggregate and detailed layers during data transitions.
- **Frontend build and TypeScript configuration restored**
    - Created missing `tsconfig.app.json` and `tsconfig.node.json` required by Vite.
    - Added `src/vite-env.d.ts` to resolve `ImportMeta` type errors for `import.meta.env`.
    - Cleaned up unused store variables in `IntelligencePanel.tsx` to satisfy strict type checking.

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
**Do NOT select:** Actor1Name, Actor2Name, Actor1Geo_FullName, Actor2Geo_FullName, MentionDocLen, or any column not in the list above, unless explicitly required. Every extra column costs money in BigQuery.

### BigQuery query safety rules (MANDATORY)
1. **Always filter by SQLDATE** using integer comparison: `WHERE SQLDATE >= 20250101`
2. **Never use `BETWEEN` on SQLDATE** — use `>=` and `<` with integer literals
3. **Never `SELECT *`** — always explicit column list
4. **Wrap all BigQuery calls with cost estimation** using `dry_run=True` before executing
5. **Daily batch job max scan budget:** 2 GB per run (hard limit in code)
6. **Fallback queries only:** BigQuery is only queried for dates older than 90 days. All recent data comes from local Parquet.

### BigQuery scan cost analysis (per table, per query type)

This section documents exactly how much each table costs to scan so future code never accidentally exceeds the 1 TB free quota.

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

### Cold tier rules (MANDATORY — do not relax these)

The cold tier is the most expensive access pattern in the system. These rules are non-negotiable:

1. **Events table only** — never query GKG or EventMentions through the cold tier. GKG costs ~2.5 GB per daily partition; across a 30-day cold query that's 75 GB from a single request.
2. **Maximum 30-day date window per cold query** — enforce in the API layer before the query is built. Reject requests for wider ranges.
3. **Maximum 3 cold queries per user per month** — track in a lightweight counter (in-memory dict or simple file, not a database). Reset monthly.
4. **Always use `dry_run=True`** before executing any cold query. Abort if estimated bytes > 2 GB (the `BQ_MAX_SCAN_BYTES` env var).
5. **Cache cold results** — after a cold query runs, cache the result as a Parquet file keyed by `{country_code}_{start_date}_{end_date}`. Subsequent identical requests serve the cache, not BigQuery.
6. **Result of cold queries is Events-only data** — do not attempt to enrich cold results with GKG themes/persons/orgs. Return raw event data only.

### What the Events table provides without GKG (cold tier capabilities)

The Events table alone covers ~80% of the dashboard's intelligence value. Everything below is available from cold tier queries:

**Directly from Events columns:**
- Conflict vs cooperation ratio per country (`QuadClass` 1–4)
- Conflict intensity score per event (`GoldsteinScale` -10 to +10)
- Sentiment / hostility of news coverage (`AvgTone`)
- How widely reported an event was (`NumMentions`, `NumSources`)
- Specific event type — 300+ CAMEO codes (`EventCode`, `EventRootCode`)
- Where event happened — lat/long and country (`ActionGeo_Lat/Long`, `ActionGeo_CountryCode`)
- Which countries' actors were involved (`Actor1Geo_CountryCode`, `Actor2Geo_CountryCode`)
- Actor type — government, military, rebel, civilian (`Actor1Type1Code`, `Actor2Type1Code`)
- Time series of daily event counts per country (`SQLDATE` aggregation)

**Derived insights computable from Events alone:**
- **Country risk score** — weighted average of GoldsteinScale, QuadClass ratio, AvgTone, NumMentions over any date range
- **Bilateral tension tracker** — count Actor1CC → Actor2CC conflict events over time; detect escalation or de-escalation between country pairs
- **Early warning signal** — 7-day rolling average of AvgTone dropping below threshold flags a country before conflict peaks
- **Actor type breakdown** — what % of events in a country involve military vs government vs civilian actors; tracks militarization
- **Media attention spike detection** — sudden NumSources spike signals a major event even before content is analyzed
- **Event type distribution** — CAMEO codes distinguish "armed attack" from "protest" from "negotiate" from "sanction" without any GKG data
- **Cross-border event detection** — events where Actor1CountryCode ≠ ActionGeo_CountryCode reveal foreign-actor involvement

**What is genuinely lost without GKG (cold tier only — hot tier still has it):**
- Named persons involved in events (GKG V2Persons)
- Named organizations — UN, NATO, ISIS etc. (GKG V2Organizations)
- Thematic tags — TERRORISM, ELECTIONS, CLIMATE etc. (GKG V2Themes)
- TF-IDF clustering on article themes (hot tier substitute: cluster on EventCode + ActorType combinations)

**Clustering alternative for cold tier:** Instead of TF-IDF on GKG themes, cluster on `EventRootCode + Actor1Type1Code + Actor2Type1Code` combinations using KMeans. CAMEO codes are a controlled vocabulary of ~300 event types — clustering on them produces semantically clean groups (all military confrontation events, all diplomatic negotiation events, etc.) without needing GKG at all.

---

## 6. Backend Structure (FastAPI + Clean Architecture)

```
backend/
├── api/
│   ├── main.py               # FastAPI app, lifespan, CORS
│   ├── routers/
│   │   ├── events.py         # GET /events, /events/region/{cc}, /events/counts
│   │   ├── analytics.py      # GET /analytics/clusters, /analytics/forecast
│   │   ├── map.py            # GET /map/data (zoom-aware aggregations/details)
│   │   └── health.py         # GET /health diagnostics
│   └── schemas/
│       └── schemas.py        # Pydantic response models
├── application/
│   └── use_cases/
│       ├── get_events.py
│       ├── cluster_events.py
│       ├── forecast_events.py
│       └── analyze_event.py
├── domain/
│   ├── models/
│   │   └── event.py          # Event, EventFilter, EventCount, ForecastResult
│   └── ports/
│       └── ports.py          # IEventRepository and service interfaces
└── infrastructure/
    ├── config/
    │   └── settings.py       # Pydantic settings (env vars)
    ├── data_access/
    │   ├── bigquery_client.py# BigQuery wrapper with mandatory dry_run guard
    │   ├── gdelt_repository.py# Cold tier Events queries (partition-pruned)
    │   ├── duckdb_repository.py # Hot tier Parquet queries via DuckDB
    │   └── routed_repository.py # Hot/cold router + cold-tier policy + cache
    └── services/
        ├── llm_analysis_service.py
        └── scraper_service.py
```

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
HOT_TIER_CUTOFF_DAYS=90
COLD_TIER_MAX_WINDOW_DAYS=30
COLD_TIER_MONTHLY_QUERY_LIMIT=3
GROQ_API_KEY=
MAPBOX_TOKEN=
ENVIRONMENT=production
BQ_MAX_SCAN_BYTES=2000000000
```

### Implemented backend guardrails (March 2026 update)
- BigQuery query execution now enforces `dry_run=True` before every query and aborts when estimated bytes exceed `BQ_MAX_SCAN_BYTES`.
- `gdelt_repository.py` now uses explicit Events column lists and SQLDATE partition filters with `>=` and `<` bounds.
- `duckdb_repository.py` has been added under `infrastructure/data_access/` and implements `IEventRepository` against local Parquet hot-tier files.
- Hot-tier repository initialization is a hard failure when `HOT_TIER_PATH` is missing or contains no `.parquet` files.
- `routed_repository.py` now enforces a single 90-day hot/cold boundary and applies it consistently to events, map details, map aggregations, and daily counts.
- Cold-tier requests are now policy-guarded: max 30-day window, max 3 queries/user/month, and result caching in parquet keyed by request shape.
- FastAPI now captures per-request user identity for quota accounting (`x-user-id`, `x-forwarded-for`, fallback client IP).
- `/health` now includes hot-tier readiness (`path`, `available`, `parquet_files`, `cutoff_days`) in addition to BigQuery status.
- `num_articles` and `total_articles` were removed from domain/API response models to align with the column-pruned Events schema.
- Backend settings now ignore unrelated `.env` keys (for example frontend `VITE_*` keys), preventing startup failure when frontend and backend share one `.env`.
- Prophet/Pandas imports in forecasting are lazy-loaded inside `forecast()` to improve API startup latency.

---

## 7. Frontend Structure (React + Vite)

```
frontend/
├── src/
│   ├── components/
│   │   ├── Map/              # Mapbox GL map, event pins, heatmap layer
│   │   ├── Sidebar/          # Country selector, date range, filters
│   │   ├── Briefing/         # AI briefing panel per country
│   │   ├── Forecast/         # Prophet forecast chart (Recharts)
│   │   └── Trends/           # Daily event count line chart
│   ├── hooks/
│   │   ├── useEvents.ts      # SWR fetch from /events
│   │   └── useForecast.ts    # SWR fetch from /analytics/forecast
│   ├── lib/
│   │   └── api.ts            # Typed API client
│   └── App.tsx
```

### Map features
- **Event pins:** Clustered markers by ActionGeo_Lat/Long, colored by QuadClass (verbal cooperation = teal, material cooperation = green, verbal conflict = amber, material conflict = red/coral)
- **Heatmap layer:** Toggle to show event density by region
- **Click on country:** Opens sidebar with AI briefing + forecast chart

---

## 8. AI/ML Components

### Event clustering (TF-IDF + KMeans)
- Input: SOURCEURL strings from hot tier, last 7 days
- Pipeline: `TfidfVectorizer(max_features=500)` → `KMeans(n_clusters=10)`
- Output: 10 semantic clusters with top terms, used to show "what's trending globally"
- Runs on-demand (cached for 1 hour per request)

### Conflict forecasting (Prophet)
- Input: daily event counts per country, filtered to QuadClass 3+4 (conflict events)
- Output: 30-day forecast with uncertainty intervals
- Pre-computed nightly for top 50 countries
- On-demand for others (slow, cached after first run)

### LLM briefings (Groq Llama 3 70B)
- Prompt: "Summarize the geopolitical situation in {country} based on these recent events: {event_summary}. Be concise, factual, ~150 words."
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

## 10. Cost Estimation (for template)

| Component | Service | Config | Monthly USD | Monthly INR | Notes |
|---|---|---|---|---|---|
| Frontend | Vercel Hobby | Free | $0 | ₹0 | CI/CD from GitHub, global CDN |
| Backend VM compute | GCP e2-standard-2 | 2 vCPU, 8 GB, 730 hrs | $48.92 | ₹4,110 | Offset by $300 credits |
| Backend VM disk | GCP Balanced PD | 100 GB SSD | $10.00 | ₹840 | **Separate charge from compute** |
| BigQuery cold tier | BigQuery on-demand | ~30 GB scans/month (~15 GB hot batch + ~15 GB cold queries) | $0 | ₹0 | 3% of 1 TB free quota — safely under |
| GCS backup | GCS Standard | 5 GB, us-central1 | $0 | ₹0 | Under always-free 5 GB limit |
| External IP | GCP Networking | Standard VM IP | $0 | ₹0 | Free while within credit |
| Network egress | GCP Networking | ~20 GB/month | $0 | ₹0 | Free within credit allotment |
| AI / LLM | Groq free tier | Llama 3 70B | $0 | ₹0 | 14,400 req/day free |
| Monitoring | Cloud Logging | Basic allotment | $0 | ₹0 | Always free |
| **Total** | | | **$58.92** | **₹4,960** | **Offset to ₹0 by $300 credits (~5 months)** |

**Without credits (honest post-project cost):** ~₹4,960/month (~$58.92)
**At 5,000 users:** ~₹11,560/month (~$137.69) — upgrade to e2-standard-4, 200 GB disk, add Regional Load Balancer

### Cost distribution (from actual GCP calculator export)
- **Compute: 83%** (e2-standard-2 VM — $48.92)
- **Storage: 17%** (100 GB Balanced Persistent Disk — $10.00)
- **Networking / BigQuery / GCS: 0%** (all within free thresholds at academic scale)

### GCP Pricing Calculator — exact line items to add
Go to https://cloud.google.com/products/calculator and add these four items:
1. **Compute Engine:** Machine type e2-standard-2, Region us-central1, 730 hours/month → $48.92/month
2. **Compute Engine — Persistent Disk:** Balanced PD, 100 GB, us-central1 → $10.00/month *(this is a separate line item from the VM, easy to miss)*
3. **Cloud Storage:** Standard class, us-central1, 5 GB → $0.00 (under always-free 5 GB quota)
4. **BigQuery:** On-demand, ~30 GB queried/month (~15 GB hot tier daily batches across all 3 tables + ~15 GB cold tier user queries) → $0.00 (under 1 TB free quota)
5. **Networking — egress:** ~20 GB/month outbound → $0.00 (within credit)
6. Apply $300 student credit → net $0 for ~5 months

**Calculator URL (already configured):** https://cloud.google.com/calculator?dl=CjhDaVF5T1RFd1ltSmxOeTFtTWpNMExUUmpNVFV0T1dNNU1TMHpOek16WkRFd1kyVmtPVFVRQVE9PRokMzY3MDhFQTQtM0M4OC00ODlFLTgwRDAtREUwQ0YxRTA3M0Yw

**For the 5,000-user scaled estimate (separate calculator entry):**
- e2-standard-4 (4 vCPU, 16 GB) → $97.84/month
- Balanced PD 200 GB → $20.00/month
- Regional External Load Balancer (forwarding rule minimum) → $18.25/month
- Load balancer data processing → $1.60/month
- **Total: $137.69/month (~₹11,560)**

---

## 11. What NOT to use (and why)

| Tool | Why excluded |
|---|---|
| **Apache Kafka** | No streaming source. GDELT publishes batch CSVs, not an event stream. |
| **Apache Airflow** | Scheduler + webserver + workers consume ~2 GB RAM alone. OOMs the VM. Use cron. |
| **Apache Spark (cloud)** | Overkill for single-node 40 GB Parquet. DuckDB is faster and uses 0 extra RAM overhead. Spark is only for Phase 1 local evidence. |
| **Cloud SQL / PostgreSQL** | $30+/month for a managed DB we don't need. DuckDB handles all OLAP in-process. |
| **Redis** | Not needed. DuckDB metadata caches in memory automatically. |
| **e2-medium (4 GB RAM)** | Too small. FastAPI + DuckDB with 40 GB Parquet metadata + Prophet = OOM. Use e2-standard-2 (8 GB). Note: disk is billed separately — 100 GB Balanced PD adds $10/month on top of VM compute cost. |

---

## 12. GitHub Repository

**URL:** https://github.com/ArceusOmkar7/gdelt_global_news_trends

Current state (as of March 2026):
- Phase 1 (backend foundation): complete — FastAPI, BigQuery integration, event retrieval
- Phase 2 (AI analytics): complete — KMeans/TF-IDF clustering, Prophet forecasting
- Phase 3 (frontend): Mapbox React frontend exists but partially built
- **Known issue (resolved in codebase):** BigQuery full-scan risk in repository layer has been mitigated with partition filters, column pruning, and dry-run byte guard.
- **Current top pending item:** Implement production ingestion jobs (`scripts/`) and deployment wiring (cron/systemd) for daily, realtime, and nightly pipelines.

The architecture described in this CONTEXT.md may require significant refactoring of the existing code, particularly:
- Add `scripts/` directory for cron jobs and systemd timers
- Frontend needs environment variable wiring for deployed API endpoint
- Tighten production robustness around quota identity/counter durability for multi-process deployment

---

## 13. Quick reference — common tasks

**Fix BigQuery query (implemented):**
`gdelt_repository.py` now uses SQLDATE partition filters (`>=` and `<`) and explicit column selection. BigQuery calls are guarded by mandatory `dry_run=True` and `BQ_MAX_SCAN_BYTES` budget check in `bigquery_client.py`.

**Set up DuckDB hot tier (implemented repository):**
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

## 14. Current File Status

| File | Status | Notes |
|---|---|---|
| `backend/infrastructure/data_access/gdelt_repository.py` | 🟢 FIXED | Explicit column list + SQLDATE partition filters (`>=` / `<`) |
| `backend/infrastructure/data_access/bigquery_client.py` | 🟢 FIXED | Mandatory dry_run guard + scan budget (`BQ_MAX_SCAN_BYTES`) |
| `backend/infrastructure/data_access/duckdb_repository.py` | 🟢 UPDATED | Hot-tier repository implemented; map aggregation parameter ordering bug fixed |
| `backend/infrastructure/data_access/routed_repository.py` | 🟢 ADDED | Shared hot/cold router with policy enforcement and cold parquet caching |
| `backend/api/request_context.py` | 🟢 ADDED | Request-scoped user identity for cold-tier monthly quota accounting |
| `backend/infrastructure/config/settings.py` | 🟢 UPDATED | Added runtime tier settings and updated default LLM model to `gemini-2.5-flash` |
| `backend/api/main.py` | 🟢 UPDATED | Wired routed repository + request identity middleware + cold policy exception handler |
| `backend/api/routers/events.py` | 🟢 ROUTED | Uses use case backed by routed repository; no direct BigQuery dependency |
| `backend/api/routers/map.py` | 🟢 ROUTED | Uses routed repository via use case; zoom behavior unchanged (`<9` aggregate, `>=9` detail) |
| `backend/api/routers/analytics.py` | 🟢 ROUTED | Clustering/forecasting now query via routed repository abstraction |
| `backend/api/routers/health.py` | 🟢 UPDATED | Adds hot-tier diagnostics (availability + parquet count + cutoff days) |
| `scripts/daily_bq_pull.py` | 🟢 ADDED | Yesterday partition pull with explicit Events columns and dry-run budget guard |
| `scripts/realtime_fetcher.py` | 🟢 ADDED | Polls `lastupdate.txt`, ingests Events CSV zip, dedupes on `GLOBALEVENTID` |
| `scripts/nightly_ai.py` | 🟢 UPDATED | Precomputes `forecasts.parquet` and `briefings.json`; briefing model default updated to `llama-3.1-8b-instant` |
| `frontend/tsconfig.app.json` | 🟢 ADDED | Vite application TypeScript configuration |
| `frontend/tsconfig.node.json` | 🟢 ADDED | Vite node/config TypeScript configuration |
| `frontend/src/vite-env.d.ts` | 🟢 ADDED | Vite client type definitions |
| `frontend/src/` | 🟢 BUILDS | Build and TypeScript configuration restored; smoke tests pending |

## 15. Known Edge Cases (Post-Routing)

1. **Per-user cold quota identity can be coarse in production proxies.**
    - Current fallback uses client IP when `x-user-id` is absent; users behind shared NAT/proxy may share quota.
2. **Cold query counter persistence is file-based and process-local locked.**
    - Thread lock is safe in a single process, but not strongly synchronized across multiple Uvicorn workers or multiple VM instances.
3. **Cold cache retention policy is not implemented yet.**
    - Cache files can grow over time; no TTL/LRU cleanup job currently runs.
4. **Cold-cache keying is shape-based with hash digest.**
    - Correct for functional reuse, but operators should still monitor duplicate near-equivalent queries (e.g., different limits) for cache fragmentation.

---

## 16. What Next (Execution Order)

### Priority 1 — Complete ingestion scripts
1. ✅ `scripts/daily_bq_pull.py` implemented.
2. ✅ `scripts/realtime_fetcher.py` implemented.
3. ✅ `scripts/nightly_ai.py` implemented.

### Priority 2 — Ops and deployment hygiene (current top priority)
1. Add systemd unit + timer files for 15-minute fetcher.
2. Add cron examples for daily and nightly jobs.
3. Add startup readiness checks in deployment docs (health now includes hot-tier availability).
4. Add a cache cleanup job (TTL or size cap) for `CACHE_PATH/cold_queries`.
5. Add monthly cold-counter rotation/pruning task.

### Priority 3 — Frontend wiring and validation
1. Confirm frontend uses `VITE_API_URL` and `VITE_MAPBOX_ACCESS_TOKEN`.
2. Validate API response shape changes (article-count fields removed) in UI types/components.
3. Add smoke tests for: events list, map layer load, forecast chart, analyze-event flow.

### Priority 4 — Quota robustness hardening
1. Replace IP fallback with authenticated user/session ID for quota keys.
2. Move quota counters from file-only persistence to a deployment-safe shared store or single-writer service process.
3. Add metrics for cold cache hit rate, cold query rejections, and monthly quota utilization.
