# Active Context — GNIEM

## Current Status
- **Phase 4 (Ambient Intelligence)**: COMPLETED.
  - Fixed GDELT 2.1 column index misalignment in realtime fetcher.
  - Lowered anomaly detection threshold to 14 days to match hot-tier volume.
  - Verified `anomalies.json` generation with IsolationForest.
  - `SpikeAlertsCard` and `TopThreatCard` UI improved (scrollable, no emojis, full names).
  - Backend `LookupService` integrated into `DuckDbRepository` for consistent country naming.

## Last Session Summary
- Debugged empty anomaly cache.
- Corrected `scripts/realtime_fetcher.py` indices.
- Fixed backend repository crash (missing methods) and CORS errors.
- Standardized UI aesthetics: No emojis, Lucide icons only, "Name (CC)" format.

## Next Task
- UI Phase 4.3: Implement the Country Choropleth Layer (risk score Mapbox fill layer).
