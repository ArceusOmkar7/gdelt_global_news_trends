"""Unit tests for LookupService."""

import pytest
from backend.infrastructure.services.lookup_service import LookupService

class TestLookupService:
    def test_get_country_name(self):
        service = LookupService()
        assert service.get_country_name("US") == "United States"
        assert service.get_country_name(None) is None
        
    def test_get_country_display(self):
        service = LookupService()
        assert service.get_country_display("US") == "United States (US)"
        assert service.get_country_display(None) == "Unknown"
