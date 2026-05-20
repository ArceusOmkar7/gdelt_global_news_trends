# Active Context — GNIEM

## Current Status
- **Phase 5 (Dashboard Intelligence & Theme System)**: IN PROGRESS.
  - Full bento-grid dashboard is live with real-time KPI cards, category filtering, stacked area trend chart, threat monitor, and spike alerts.
  - Dark ↔ Light theme toggle is implemented with CSS variable switching and theme-aware chart rendering.
  - System Control Panel moved into a slide-in side drawer (hidden from main view, accessible via header button).
  - Intelligence Panel auto-scrolls to top on every event selection.
  - `EventTrendChart` added to the dashboard showing per-day total vs conflict event volumes.
  - Finalized light mode visibility for Map Launch cards by removing forced dark overrides and increasing text opacity.
  - Country ➔ State ➔ City drill-down filtering is fully completed. Integrated the City dropdown directly into the upper horizontal header filter bar (`GeoFilterBar`) next to Country and State. Permanently deleted the redundant `GeoDrillPanel` sidebar block.
  - Map filtering for cities is fully resolved and operational. All zoom levels (both low-zoom grid intensity aggregates and high-zoom detailed markers) now correctly respect geocoded boundaries inside the DuckDB repository.
  - Theme category pills added as a secondary filter (backed by nightly cache).

## Recent Changes (2026-05-20)
### UI / Frontend Changes
- **Dynamic Heatmap Shading & High-Fidelity Transitions**: Recalibrated the aggregated heatmap layer parameters in `GlobalEventMap.tsx`. Adjusted `heatmap-radius` zoom scaling (`4px` at zoom 0 to `25px` at zoom 9), expanded the `heatmap-weight` log density range from `6` to `10` to avoid flat-red oversaturation, and introduced a glowing Neon-Cyan ➔ Emerald ➔ Yellow ➔ Orange ➔ Crimson Red spectrum to enable rich transitions and shading.
- **Dynamic, Mode-Aware Map Legend**: Re-engineered `MapLegend.tsx` to read the active `mapMode` from the Zustand store. When in Heatmap mode, the legend dynamically switches from Cluster categories to a gorgeous horizontal Heat Density gradient bar showing Low Activity to Peak Active ranges.
- **Theme-Responsive Mapbox Map Integration**: Updated `GlobalEventMap.tsx` to dynamically switch the Mapbox style between `mapbox://styles/mapbox/dark-v11` and `mapbox://styles/mapbox/light-v11` in real time as the user toggles dark/light themes. Also updated the parent map container element in `App.tsx` to switch background color to prevent theme flashing during map loads.
- **System Panel Backdrop Blur Tweak**: Resolved the light-mode wildcard CSS rule collision where a solid dark navy color overrode the system panel's backdrop by dynamically selecting `bg-slate-900/20` in light mode (which lacks the `bg-black` string that gets intercepted by index.css).
- **Bar Chart Scale and Exact Formatting Resolved**: Modified both `PeopleMentionsChart.tsx` and `SourceMentionsChart.tsx` to completely remove dynamic `K`-scale rounding and legend badges, displaying the exact, comma-formatted counts directly on the X-axis, bar labels, and custom tooltips. This completely resolves the duplicate tick collision bug (e.g. `2K` showing twice on close values).
- **ESLint & TypeScript Type-Safety Improvements**: Removed raw `any` types in both charts, replacing them with a type-safe `unknown` and a detailed `CustomTooltipProps` interface, resolving all 4 pre-existing chart linting errors.
- **Header Geo Filter Bar Refactored**: Added the "City" dropdown directly in the upper horizontal filter bar (`GeoFilterBar.tsx`). The dropdown fetches matching cities under the selected state via React Query `citiesQuery` dynamically.
- **Sidebar Clutter Cleanup**: Removed all imports and logic of `GeoDrillPanel` from `IntelligencePanel.tsx`. The drawer now cleanly triggers only for concrete events and regional dossiers, ignoring location-only adjustments.
- **Redundant Components Pruned**: Permanently deleted the unused component file `GeoDrillPanel.tsx` from the codebase.
- **Unit Test Alignments**: Fixed pre-existing failures in `test_map_api.py` by aligning requested paths from `/api/v1/map/data` to `/api/v1/events/map` and updating the zoom level to `10.0` for detailed mode testing.

### Backend Changes
- **Map Geocoding Queries Resolved**: Applied `_apply_geo_state_city_filter` in both `get_map_aggregations` and `get_event_details` inside `duckdb_repository.py`. Selecting a geocoded city now correctly filters map markers and grid cells within city boundaries.
- **SQL Parameter Safety**: Maintained full parameterization on geolocated query constructs to block SQL injection.

## Last Session Summary (2026-04-30)

### UI / Frontend Changes
- **Category system revamped:** Categories row now uses `ALL | CONFLICT | DIPLOMACY | COOPERATION | PRESSURE`, mapped to CAMEO root code groups (multi-code filters).
- **Conditional bento grid:** When any category other than ALL is selected, the standard bento grid (TopThreat + SpikeAlerts) is replaced by a full-width `TrendingNewsFeed` component showing live-filtered event intel.
- **`TrendingNewsFeed` component:** Created `frontend/src/components/tables/TrendingNewsFeed.tsx` — renders category-filtered events with Goldstein/tone sentiment, source extraction, and "Launch Map" buttons.
- **Geo filter UI:** Added `GeoFilterBar` (country/state pill rows) and `GeoDrillPanel` (city pills when state selected). Geo selections live in Zustand.
- **Theme category pills:** Added secondary theme category row (POLITICS, ECONOMY, HEALTH, ENVIRONMENT, TECHNOLOGY, ENERGY, HUMAN RIGHTS) and wired to API query params.
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
  - **Media Evidence layout:** Intelligence Panel now renders one primary image with three supporting thumbnails (2x2) in the Media Evidence section.
  - **Live News Wall:** Added a live YouTube embed grid in the main dashboard column that switches channels based on the selected country (GLOBAL/US/IR/IS/UK/RS/IN).

### Backend Changes
- **Reverse geocoding:** Added `reverse_geocoder` dependency and `ReverseGeocodeService` (offline). DuckDB adds `get_geo_drill` for country/state/city drill-down.
- **Geo drill endpoint:** New `GET /api/v1/events/geo-drill` (hot tier only) for drill-down options.
- **Theme categories cache:** Nightly job writes `theme_categories.json`; new `GET /api/v1/analytics/theme-categories` endpoint serves it.
- **Filter upgrades:** Event filters now use `event_root_codes` (list), plus geo and theme category filters across hot-tier queries.
- **Jina AI Reader scraper:** Scraper refactor uses Jina Reader JSON, extracts images from markdown, scores candidates, and normalizes embed URLs to iframe-ready links.

## Known Issues / Technical Debt
- ~10 ESLint `any` type warnings remain across the codebase (cleanup sprint needed).
- The CAMEO `most_active_country` KPI always returns `US` for most categories because GDELT's English-language news coverage is US-heavy. Consider excluding US from this metric or using a secondary metric.

## Next Task
- Fix category mappings: use `themes` column text pattern matching for SPORTS / TECH / HEALTH.
- UI Phase 4.3: Implement Country Choropleth Layer (risk score Mapbox fill layer).
- Add request-level timing instrumentation per API route.
- Linting sprint: resolve remaining `any` type errors.
