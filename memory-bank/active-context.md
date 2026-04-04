# Active Context — GNIEM

## Current Status
- **Phase 1, 2, 3:** COMPLETED.
- **UI Phase 4 (Ambient Intelligence):** COMPLETED.
  - GlobalStatsTicker (Fixed bottom bar).
  - TopThreatCard (Sidebar ranked threats).
  - Activity Spike Alerts (2.0x detection).
  - IsolationForest Anomaly Detection (Nightly pre-compute).
  - Map & Sidebar Anomaly Visuals (Pulsing amber glow, badges).
- **Next: UI Phase 4.3 Country Choropleth Layer.**

## Last Session Summary
- Implemented `GET /analytics/spikes` with 2.0x threshold logic and 15-min cache.
- Implemented IsolationForest anomaly detection in `scripts/nightly_ai.py` with 5-feature vectors.
- Added `GET /analytics/anomalies` to serve nightly pre-computed flags.
- Created `SpikeAlertsCard` component with 5-min polling and [OPEN DOSSIER] integration.
- Updated `GlobalEventMap` with pulsing amber markers for anomalous countries.
- Updated `TopThreatCard` with ◈ ANOMALY badges.
- Recorded patterns/conventions via `mulch`.
- Updated `CONTEXT.md` section 14 and 17.

## Next Task
- UI Phase 4.3: Implement the Country Choropleth Layer (risk score Mapbox fill layer).
