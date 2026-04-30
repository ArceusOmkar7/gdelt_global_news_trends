"""Offline reverse geocoding using reverse_geocoder (GeoNames-based, no API calls)."""
from __future__ import annotations

import reverse_geocoder as rg


class ReverseGeocodeService:
    """Converts (lat, lon) to (country_code, state, city) using GeoNames data."""

    def lookup(self, lat: float, lon: float) -> dict:
        """
        Returns dict with keys: cc (2-letter ISO), name (city), admin1 (state/province).
        Falls back to empty strings on failure.
        """
        try:
            results = rg.search((lat, lon), mode=1, verbose=False)
            if results:
                r = results[0]
                return {
                    "country_code": r.get("cc", ""),
                    "city": r.get("name", ""),
                    "state": r.get("admin1", ""),
                }
        except Exception:
            pass
        return {"country_code": "", "city": "", "state": ""}

    def lookup_batch(self, coords: list[tuple[float, float]]) -> list[dict]:
        """Batch reverse geocode for efficiency."""
        try:
            results = rg.search(coords, mode=1, verbose=False)
            return [
                {
                    "country_code": r.get("cc", ""),
                    "city": r.get("name", ""),
                    "state": r.get("admin1", ""),
                }
                for r in results
            ]
        except Exception:
            return [{"country_code": "", "city": "", "state": ""} for _ in coords]


reverse_geocode_service = ReverseGeocodeService()