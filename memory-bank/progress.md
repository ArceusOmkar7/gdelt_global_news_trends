# Project Progress — GNIEM

## Current State
- **Hot Tier:** Working. Daily BQ pull and 15-min fetcher are functional.
- **Dashboard:** Mapbox map with zoom-adaptive rendering is live.
- **Dossier Panel:** Regional dossier and event intelligence views are implemented.
- **AI Analytics:** KMeans/TF-IDF clustering and Prophet forecasting are integrated.
- **Ambient Intelligence:** GlobalStatsTicker, TopThreatCard, and SpikeAlertsCard are functional.
- **Anomaly Detection:** IsolationForest nightly pre-compute and visual integration complete.

## Done
- [x] Backend Foundation (FastAPI, DuckDB, BigQuery Routing)
- [x] Data Pipeline (Daily BQ Pull, Realtime Fetcher, Nightly AI jobs)
- [x] Frontend Phase 1 (Map, Basic Panels)
- [x] UI Phase 1 (Navbar cleanup, sync indicators)
- [x] UI Phase 2 (Contextual labels + delta indicators)
- [x] UI Phase 4.1 (GlobalStatsTicker)
- [x] UI Phase 4.2 (TopThreatCard)
- [x] UI Phase 4.4 (Activity Spike Alerts)
- [x] IsolationForest Anomaly Detection

## In Progress
- [x] UI Phase 4.3 (Anomaly Detection Backend Fixes)
- [ ] UI Phase 4.3 (Country Choropleth Layer)

## Pending
- [ ] UI Phase 4.5 (Settings Modal Refactor)
- [ ] GCP VM Deployment (Systemd, Nginx, SSL)
- [ ] Vercel Deployment
- [ ] Academic Evidence (Spark/HDFS on WSL)
- [ ] Written reports (Cost, AI, Dataset)
