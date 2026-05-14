"""Unit tests for ReverseGeocodeService."""

import pytest
from unittest.mock import patch
from backend.infrastructure.services.reverse_geocode_service import ReverseGeocodeService

class TestReverseGeocodeService:
    def setup_method(self):
        self.service = ReverseGeocodeService()

    @patch("backend.infrastructure.services.reverse_geocode_service.rg.search")
    def test_lookup_valid(self, mock_search):
        mock_search.return_value = [{"cc": "US", "name": "San Francisco", "admin1": "California"}]
        res = self.service.lookup(37.7749, -122.4194)
        
        assert res["country_code"] == "US"
        assert res["city"] == "San Francisco"
        assert res["state"] == "California"
        mock_search.assert_called_once_with((37.7749, -122.4194), mode=1, verbose=False)

    @patch("backend.infrastructure.services.reverse_geocode_service.rg.search")
    def test_lookup_empty_result(self, mock_search):
        mock_search.return_value = []
        res = self.service.lookup(0.0, 0.0)
        
        assert res["country_code"] == ""
        assert res["city"] == ""
        assert res["state"] == ""

    @patch("backend.infrastructure.services.reverse_geocode_service.rg.search")
    def test_lookup_batch_valid(self, mock_search):
        mock_search.return_value = [
            {"cc": "US", "name": "San Francisco", "admin1": "California"},
            {"cc": "JP", "name": "Tokyo", "admin1": "Tokyo"}
        ]
        
        coords = [(37.7749, -122.4194), (35.6895, 139.6917)]
        res = self.service.lookup_batch(coords)
        
        assert len(res) == 2
        assert res[0]["country_code"] == "US"
        assert res[1]["country_code"] == "JP"
        mock_search.assert_called_once_with(coords, mode=1, verbose=False)

    def test_lookup_batch_empty(self):
        res = self.service.lookup_batch([])
        assert res == []
