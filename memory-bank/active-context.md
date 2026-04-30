# Active Context — GNIEM

## Current Status
- **Phase 5 (Dashboard Intelligence & Theme System)**: IN PROGRESS.
  - Full bento-grid dashboard is live with real-time KPI cards, category filtering, stacked area trend chart, threat monitor, and spike alerts.
  - Dark ↔ Light theme toggle is implemented with CSS variable switching and theme-aware chart rendering.
  - System Control Panel moved into a slide-in side drawer (hidden from main view, accessible via header button).
  - Intelligence Panel auto-scrolls to top on every event selection.
  - `EventTrendChart` added to the dashboard showing per-day total vs conflict event volumes.

## Last Session Summary (2026-04-30)

### UI / Frontend Changes
- **Category system revamped:** Categories row (`ALL | WAR | POLITICS | ECONOMY | SPORTS | TECH | HEALTH`) now maps to GDELT CAMEO root codes. Selecting a category filters both the KPI global-pulse metrics and the trending news feed.
- **Conditional bento grid:** When any category other than ALL is selected, the standard bento grid (TopThreat + SpikeAlerts) is replaced by a full-width `TrendingNewsFeed` component showing live-filtered event intel.
- **`TrendingNewsFeed` component:** Created `frontend/src/components/tables/TrendingNewsFeed.tsx` — renders category-filtered events with Goldstein/tone sentiment, source extraction, and "Launch Map" buttons.
- **System Panel Drawer:** Removed `SystemControlPanel` from the main bento grid. Replaced with a `[ ⌘ System ]` button in the header that opens a right-side slide-in drawer (blurred backdrop, `×` dismiss). Uses `showSystemPanel` local state.
- **Date Slider popover:** Timeline control moved behind a header date button. Click to reveal; click outside or re-click to dismiss.
- **Launch Interactive Map cards:** Both the ALL view and category view use the same premium dark/cyber hero card design (world-map SVG background, glassmorphism, cyan glow on hover). Uses `map-launch-card` CSS class.
- **Dark ↔ Light theme toggle:**
  - `Sun`/`Moon` button added to the header between System and Map Mode controls.
  - `isDarkTheme` / `setIsDarkTheme` added to `useStore`.
  - `data-theme="dark"|"light"` is applied to `<html>` via a `useEffect` in `App.tsx`.
  - Full CSS variable remap in `index.css` for light mode (surfaces, borders, glass panels, scrollbars, glow effects).
  - `IntelligencePanel` charts (`LineChart`, `AreaChart`) are fully theme-aware via a `ct` (chart-token) object derived from `isDarkTheme`.
  - The Conflict Forecast chart's dark clip fill (`rgba(10,10,10,0.8)`) now switches to the light background colour to prevent the "black band" artifact.
- **Intelligence Panel scroll reset:** Added `useRef` + `useEffect` in `IntelligencePanel.tsx` that resets `scrollTop = 0` whenever `selectedEvent` changes, fixing the panel staying scrolled to the bottom on event navigation.
- **`EventTrendChart` component:** New `frontend/src/components/ambient/EventTrendChart.tsx`.
  - Stacked AreaChart using Recharts.
  - Outer (larger) area = total daily events (cyan gradient, dark / blue gradient, light).
  - Inner (smaller) area = conflict events, QuadClass >= 3 (red gradient).
  - Custom tooltip shows total, conflict count, and conflict ratio %.
  - Y-axis formatted as `K`/`M`. Fully theme-aware via `isDarkTheme`.
  - Placed between KPI row and bento grid on the main dashboard.
  - Responds to active `eventRootCode` (category filter).

### Backend Changes
- **`DuckDbRepository.get_daily_trend()`**: New method in `backend/infrastructure/data_access/duckdb_repository.py`.
  - Groups by `SQLDATE`, counts total events and `SUM(CASE WHEN QuadClass >= 3 THEN 1 ELSE 0 END)` for conflict.
  - Accepts `event_root_code` filter.
  - Returns `[{date: "YYYY-MM-DD", total: int, conflict: int}]` sorted ascending.
- **`GET /api/v1/events/daily-trend`**: New FastAPI endpoint in `backend/api/routers/events.py`.
  - Params: `start_date`, `end_date`, optional `event_root_code`.
  - Returns `{"data": [...]}`.
- **`apiService.getDailyTrend()`**: New frontend service method in `frontend/src/services/api.ts`.
- **`apiService.getGlobalEvents()`**: Added for category-filtered event feed retrieval.
- **Cold-tier query limit raised:** `cold_tier_monthly_query_limit` `le` raised to `999999` (was `100`).
- **CAMEO category accuracy audit:** Confirmed that GDELT's CAMEO taxonomy is actor-action based, not topic-based. Sports/Tech/Health have no native CAMEO mapping — documented as known limitation.

## Known Issues / Technical Debt
- `SPORTS`, `TECH`, `HEALTH` category filters map to approximate CAMEO codes that don't accurately represent the topic. A `themes` text-pattern approach is needed for proper topic filtering.
- ~10 ESLint `any` type warnings remain across the codebase (cleanup sprint needed).
- The CAMEO `most_active_country` KPI always returns `US` for most categories because GDELT's English-language news coverage is US-heavy. Consider excluding US from this metric or using a secondary metric.

## Next Task
- Fix category mappings: use `themes` column text pattern matching for SPORTS / TECH / HEALTH.
- UI Phase 4.3: Implement Country Choropleth Layer (risk score Mapbox fill layer).
- Add request-level timing instrumentation per API route.
- Linting sprint: resolve remaining `any` type errors.
