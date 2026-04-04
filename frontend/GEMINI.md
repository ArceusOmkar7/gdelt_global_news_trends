# Frontend Mandates — GNIEM

## Development Standards
- **Framework:** React + Vite + TypeScript.
- **State Management:** Zustand only. No Redux or Context API for global state.
- **Charts:** Recharts only.
- **Map:** Mapbox GL JS only. No other map libraries (Leaflet, OpenLayers).
- **Styling:** Vanilla CSS / CSS Modules preferred for custom aesthetics.

## Critical Rules
- **Label Mapping:** Always use `lib/gdelt-lookups.ts` for CAMEO codes, QuadClass, and actor types. NEVER hardcode labels in components.
- **Color System:**
  - Teal: Cooperative events.
  - Amber: Neutral-negative events.
  - Red: Conflict/Threat events.
  - Green: Improvement/Positive trends.
- **Threat Level Thresholds:**
  - 0-30: LOW (Green)
  - 31-50: MODERATE (Amber)
  - 51-70: ELEVATED (Orange)
  - 71-100: CRITICAL (Red)
- **Persistence:** Never use `localStorage` or `sessionStorage` for application state.
- **Map Interactions:** In aggregate cluster handlers, always call `setSelectedEvent(null)` BEFORE `setSelectedCountry(code)`.

## Data Handling
- **Theme Cleanup:** Use `cleanGkgTheme()` to strip GDELT prefixes.
- **Deduplication:** Always deduplicate themes/entities before rendering: `[...new Set(items)].slice(0, 6)`.
