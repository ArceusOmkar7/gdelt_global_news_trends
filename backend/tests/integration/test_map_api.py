"""Integration tests for the Map API — mocks the repository to test the full HTTP stack.
"""

import os
import tempfile
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Ensure settings have required values before importing app/settings singleton.
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
_HOT_TIER_DIR = tempfile.mkdtemp(prefix="gniem-hot-tier-")
_HOT_TIER_FILE = os.path.join(_HOT_TIER_DIR, "events_test.parquet")
if not os.path.exists(_HOT_TIER_FILE):
    pd.DataFrame(
        [
            {
                "GLOBALEVENTID": 1,
                "SQLDATE": 20240101,
                "Actor1CountryCode": "US",
                "Actor2CountryCode": "CA",
                "EventRootCode": "19",
                "EventCode": "190",
                "GoldsteinScale": -3.0,
                "NumMentions": 10,
                "NumSources": 2,
                "AvgTone": -1.0,
                "ActionGeo_CountryCode": "US",
                "ActionGeo_Lat": 10.0,
                "ActionGeo_Long": 20.0,
                "SOURCEURL": "https://example.com",
                "Actor1Type1Code": "GOV",
                "Actor2Type1Code": "MIL",
            }
        ]
    ).to_parquet(_HOT_TIER_FILE, index=False)
os.environ.setdefault("HOT_TIER_PATH", _HOT_TIER_DIR)

from backend.api.main import app
import backend.api.main as main_module
from backend.api.routers.events import _get_use_case as _get_events_use_case
from backend.api.routers.map import _get_use_case as _get_map_use_case
from backend.application.use_cases.get_events import GetEventsUseCase
from backend.domain.models.event import MapAggregation, MapEventDetail
from backend.domain.ports.ports import IEventRepository


@pytest.fixture
def mock_repository():
    return MagicMock(spec=IEventRepository)


@pytest.fixture
def client(mock_repository):
    # Use the same repository for both use cases in main.py
    use_case = GetEventsUseCase(mock_repository)
    main_module.settings.hot_tier_path = _HOT_TIER_DIR
    main_module.settings.cache_path = os.path.join(_HOT_TIER_DIR, "cache")
    main_module.settings.gcp_project_id = "test-project"
    with TestClient(app) as c:
        # Override AFTER lifespan has run to ensure we win
        app.dependency_overrides[_get_events_use_case] = lambda: use_case
        app.dependency_overrides[_get_map_use_case] = lambda: use_case
        yield c
    app.dependency_overrides.clear()


def test_get_map_data_aggregated(client, mock_repository):
    # Setup
    mock_repository.get_map_aggregations.return_value = [
        MapAggregation(lat=10.0, lon=20.0, intensity=5.0)
    ]
    
    # Execute
    response = client.get(
        "/api/v1/events/map",
        params={
            "bbox_n": 15.0,
            "bbox_s": 5.0,
            "bbox_e": 25.0,
            "bbox_w": 15.0,
            "zoom": 3,
        }
    )
    
    # Verify
    assert response.status_code == 200
    payload = response.json()
    assert payload["zoom"] == 3
    assert payload["is_aggregated"] is True
    assert payload["count"] == 1
    assert payload["data"][0]["lat"] == 10.0
    assert payload["data"][0]["lon"] == 20.0
    assert payload["data"][0]["intensity"] == 5.0
    
    mock_repository.get_map_aggregations.assert_called_once()


def test_get_map_data_detailed(client, mock_repository):
    # Setup
    mock_repository.get_event_details.return_value = [
        MapEventDetail(
            global_event_id=123,
            sql_date=date(2024, 1, 1),
            lat=12.0,
            lon=22.0,
            goldstein_scale=4.5
        )
    ]
    
    # Execute
    response = client.get(
        "/api/v1/events/map",
        params={
            "bbox_n": 15.0,
            "bbox_s": 5.0,
            "bbox_e": 25.0,
            "bbox_w": 15.0,
            "zoom": 10,
        }
    )
    
    # Verify
    assert response.status_code == 200
    payload = response.json()
    assert payload["zoom"] == 10
    assert payload["is_aggregated"] is False
    assert payload["count"] == 1
    assert payload["data"][0]["global_event_id"] == 123
    assert payload["data"][0]["lat"] == 12.0
    assert payload["data"][0]["lon"] == 22.0
    
    mock_repository.get_event_details.assert_called_once()
