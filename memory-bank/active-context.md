# Active Context — GNIEM

## Current Status
- **Phase 4 (Ambient Intelligence)**: COMPLETED with post-phase stabilization updates.
  - Added bottom **Timeline Window** dual-handle date slider with quick presets (`1D/3D/7D/14D/FULL`) and collapsible panel behavior.
  - Added automatic date alignment to latest hot-tier sync date for stale ingestion scenarios.
  - Expanded anomaly API schema to include `country_name` and `country_display`; anomaly/spike labels now render in `Country Name (CC)` format.
  - Added media extraction support (images and embeds) to the Apify scraper and Groq LLM analysis pipeline, with UI updates in `IntelligencePanel`.
  - Upgraded cold tier limits (increased max window days and monthly query limit) and improved date resolution in routed repository using hot tier data.
  - Added relative path support for hot tier data access in DuckDB repository and enhanced ingestion stats.

## Last Session Summary
- Implemented full media extraction support (images and video embeds) from articles, updating the backend scraper, LLM service, and frontend UI components.
- Adjusted backend settings and `gdelt_repository` to properly use cold tier max window days.
- Refactored `routed_repository` to improve date resolution logic.
- Fixed `scraper_service` wait duration parameter (`wait_secs` instead of `wait_duration`) for Apify crawling requests to prevent crash/timeouts.
- Added debugging scripts for table inspection and index verification.

## Next Task
- UI Phase 4.3: Implement the Country Choropleth Layer (risk score Mapbox fill layer).
- Add lightweight request-level timing instrumentation per API route (for cold vs warm visibility).
