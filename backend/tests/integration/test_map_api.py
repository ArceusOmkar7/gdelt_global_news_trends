"""Integration tests for the Map API — mocks the repository to test the full HTTP stack.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
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
            "zoom": 6,
        }
    )
    
    # Verify
    assert response.status_code == 200
    payload = response.json()
    assert payload["zoom"] == 6
    assert payload["is_aggregated"] is False
    assert payload["count"] == 1
    assert payload["data"][0]["global_event_id"] == 123
    assert payload["data"][0]["lat"] == 12.0
    assert payload["data"][0]["lon"] == 22.0
    
    mock_repository.get_event_details.assert_called_once()
