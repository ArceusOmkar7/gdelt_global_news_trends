# Active Context — GNIEM

## Current Status
- **Phase 4 (Ambient Intelligence)**: COMPLETED.
  - Fixed GDELT 2.1 column index misalignment in realtime fetcher.
  - Lowered anomaly detection threshold to 14 days to match hot-tier volume.
  - Verified `anomalies.json` generation with IsolationForest (now includes full country names).
  - `SpikeAlertsCard` and `TopThreatCard` UI standardized: scrollable, icons-only, "Name (CC)" format.
  - Frontend types updated to reflect new backend metadata.

## Last Session Summary
- Debugged country name formatting in `SpikeAlertsCard`.
- Updated `scripts/nightly_ai.py` to populate `country_display`.
- Restored code comments for maintainability.
- Synchronized frontend interfaces with backend response models.

## Next Task
- UI Phase 4.3: Implement the Country Choropleth Layer (risk score Mapbox fill layer).
