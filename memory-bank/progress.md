# Project Progress — GNIEM

## Current State
- **Hot Tier:** Working. Daily BQ pull and 15-min fetcher are functional.
- **Dashboard:** Full bento-grid dashboard with KPI cards, category filtering, stacked area trend chart, threat monitor, spike alerts, and interactive map launch card.
- **Theme System:** Dark ↔ Light theme toggle live with full CSS variable mapping and theme-aware Recharts charts.
- **Dossier Panel:** Regional dossier and event intelligence views are implemented. Auto-scrolls to top on event navigation.
- **AI Analytics:** KMeans/TF-IDF clustering and Prophet forecasting are integrated.
- **Ambient Intelligence:** GlobalStatsTicker, TopThreatCard, SpikeAlertsCard, and EventTrendChart are functional.
- **Anomaly Detection:** IsolationForest nightly pre-compute and visual integration complete.
- **Timeline Control:** Global dual-handle date slider with quick ranges — launched via header date button popover.
- **Briefings Integration:** Nightly briefing cache is now exposed and rendered in Regional Dossier.
- **Load Stabilization:** Startup date-window gating prevents duplicate stale+aligned request burst.
- **System Panel:** Moved into a slide-in right drawer, accessible via `[ ⌘ System ]` header button.

## Done
- [x] Backend Foundation (FastAPI, DuckDB, BigQuery Routing)
- [x] Data Pipeline (Daily BQ Pull, Realtime Fetcher, Nightly AI jobs)
- [x] Frontend Phase 1 (Map, Basic Panels)
- [x] UI Phase 1 (Navbar cleanup, sync indicators)
- [x] UI Phase 2 (Contextual labels + delta indicators)
- [x] UI Phase 4.1 (GlobalStatsTicker)
- [x] UI Phase 4.2 (TopThreatCard)
- [x] UI Phase 4.4 (Activity Spike Alerts + UI Refactor)
- [x] IsolationForest Anomaly Detection
- [x] Timeline Window Slider (dual handle + presets + popover from header)
- [x] Nightly Briefings API + Regional Dossier rendering
- [x] Anomaly response metadata expansion (`country_name`, `country_display`)
- [x] Date-window readiness gating for startup fetch stabilization
- [x] Media extraction (images & embeds) integration in article scraper and Intelligence Panel UI
- [x] Cold tier and routing enhancements (max window limits, date resolution, relative paths)
- [x] Local debugging scripts for Parquet and GDELT index verification
- [x] Dashboard-first UI with categories row and responsive bento grid
- [x] Category system mapped to CAMEO root codes (ALL/WAR/POLITICS/ECONOMY/SPORTS/TECH/HEALTH)
- [x] Category tabs updated to CAMEO groups (ALL/CONFLICT/DIPLOMACY/COOPERATION/PRESSURE)
- [x] Geo filter bar + drill-down panel (country/state/city) with reverse geocoding
- [x] Geo drill hot-tier endpoint (`/events/geo-drill`) and offline reverse geocoder service
- [x] Theme category nightly cache + analytics endpoint (`/analytics/theme-categories`)
- [x] Theme category pills as secondary filter in dashboard
- [x] Conditional bento grid: category view replaces widgets with TrendingNewsFeed
- [x] TrendingNewsFeed component (Goldstein/tone sentiment, source, "Launch Map" per event)
- [x] `getGlobalEvents` API service + category-filtered event endpoint
- [x] System Control Panel moved to slide-in right drawer (header button toggle)
- [x] Dark ↔ Light theme toggle (CSS variables, `isDarkTheme` store, `data-theme` on `<html>`)
- [x] Theme-aware IntelligencePanel charts (LineChart + AreaChart axis, fills, tooltips)
- [x] Conflict Forecast dark clip-fill bug fixed for light mode
- [x] Intelligence Panel scroll-to-top on event selection (`useRef` + `useEffect`)
- [x] `EventTrendChart` — stacked area chart (total events vs conflict events) on main dashboard
- [x] `GET /api/v1/events/daily-trend` backend endpoint + `DuckDbRepository.get_daily_trend()`
- [x] `getDailyTrend` frontend API service method
- [x] Launch Interactive Map card: same premium design in both ALL and category views
- [x] Map-launch card optimized for light theme (removed forced dark background, increased text opacity to 70%)
- [x] Cold-tier monthly query limit raised to 999999 (was 100)

## In Progress
- [ ] UI Phase 4.3 (Country Choropleth Layer)

## Pending
- [ ] Linting sprint: resolve ~10 remaining ESLint `any` type warnings
- [ ] UI Phase 4.5 (Settings Modal Refactor)
- [ ] GCP VM Deployment (Systemd, Nginx, SSL)
- [ ] Vercel Deployment
- [ ] Academic Evidence (Spark/HDFS on WSL)
- [ ] Written reports (Cost, AI, Dataset)
