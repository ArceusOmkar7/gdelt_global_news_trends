import logging
import requests
from pathlib import Path
from typing import Dict, Optional
from backend.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

class LookupService:
    """Service to handle GDELT lookup files (countries, CAMEO codes, etc.)."""
    
    def __init__(self):
        self._country_codes: Dict[str, str] = {}
        self._lookup_dir = Path(settings.cache_path) / "lookups"
        self._lookup_dir.mkdir(parents=True, exist_ok=True)
        self._country_file = self._lookup_dir / "LOOKUP-COUNTRIES.txt"

    def _ensure_country_codes(self):
        """Download and load country codes if not already present."""
        if not self._country_codes:
            if not self._country_file.exists():
                self.refresh_country_codes()
            self._load_from_disk()

    def refresh_country_codes(self):
        """Force a redownload of the country codes lookup file."""
        url = settings.action_geo_country_codes_url
        logger.info(f"Downloading country codes from {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self._country_file.write_text(response.text, encoding="utf-8")
            logger.info(f"Saved country codes to {self._country_file}")
            # Reload into memory after refresh
            self._load_from_disk()
        except Exception as e:
            logger.error(f"Failed to download country codes: {e}")

    def _load_from_disk(self):
        """Load country codes from the local cached file."""
        if not self._country_file.exists():
            return

        codes = {}
        try:
            content = self._country_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if not line.strip():
                    continue
                # Format is: Code\tName
                parts = line.split("\t")
                if len(parts) >= 2:
                    code, name = parts[0].strip(), parts[1].strip()
                    codes[code] = name
            self._country_codes = codes
        except Exception as e:
            logger.error(f"Error parsing country codes file: {e}")

    def get_country_name(self, code: str) -> Optional[str]:
        """Get the full name for a 2-letter country code."""
        self._ensure_country_codes()
        return self._country_codes.get(code)

    def get_country_display(self, code: Optional[str]) -> str:
        """Return format 'Name (Code)' or just 'Code' if name not found."""
        if not code:
            return "Unknown"
        
        name = self.get_country_name(code)
        if name:
            return f"{name} ({code})"
        return code

# Singleton instance
lookup_service = LookupService()
