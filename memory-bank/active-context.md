# Active Context — GNIEM

## Current Status
- **Phase 4 (Ambient Intelligence)**: COMPLETED.
  - Fixed GDELT 2.1 column index misalignment in realtime fetcher.
  - Lowered anomaly detection threshold to 14 days to match hot-tier volume.
  - Verified `anomalies.json` generation with IsolationForest.
  - Map and Sidebar anomaly indicators are now functional with real data.

## Last Session Summary
- Debugged empty anomaly cache.
- Corrected `scripts/realtime_fetcher.py` indices (ActionGeo_CountryCode at 53, Lat at 56, Long at 57, etc).
- Re-ran nightly AI job and confirmed successful data generation for 40+ countries.

## Next Task
- UI Phase 4.3: Implement the Country Choropleth Layer (risk score Mapbox fill layer).
