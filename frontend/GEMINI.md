# Frontend Mandates — GNIEM

## Development Standards
- **Framework:** React + Vite + TypeScript.
- **State Management:** Zustand only. No Redux or Context API for global state.
- **Charts:** Recharts only.
- **Map:** Mapbox GL JS only. No other map libraries (Leaflet, OpenLayers).
- **Styling:** Vanilla CSS / CSS Modules preferred for custom aesthetics.

## UI & Aesthetics
- **No Emojis:** Never use emojis in the UI (e.g., no ⚡, ◈, ▲, ▼). Use Lucide icons instead.
- **Country Naming:** Always display countries in "Country Name (CC)" format (e.g., "India (IN)").
- **Scrollable Components:** Sidebar cards with dynamic lists must be scrollable (max-height) rather than expanding the full page.

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
