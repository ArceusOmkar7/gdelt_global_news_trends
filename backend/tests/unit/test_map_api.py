"""Unit tests for the map router."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domain.models.event import MapAggregation, MapEventDetail
from backend.domain.ports.ports import IEventRepository

client = TestClient(app)

def _mock_routed_repo():
    mock = MagicMock(spec=IEventRepository)
    mock.get_map_aggregations.return_value = [
        MapAggregation(lat=10.0, lon=10.0, intensity=5.0)
    ]
    mock.get_event_details.return_value = [
        MapEventDetail(global_event_id=1, sql_date="2024-01-01", lat=10.0, lon=10.0)
    ]
    return mock

@pytest.fixture
def override_dependencies():
    from backend.api.routers.map import _get_use_case
    from backend.application.use_cases.get_events import GetEventsUseCase
    
    repo_mock = _mock_routed_repo()
    use_case = GetEventsUseCase(repo_mock)
    
    app.dependency_overrides[_get_use_case] = lambda: use_case
    yield repo_mock
    app.dependency_overrides.clear()

def test_map_data_aggregated(override_dependencies):
    repo_mock = override_dependencies
    
    response = client.get("/api/v1/events/map?zoom=2.0&bbox_n=90&bbox_s=-90&bbox_e=180&bbox_w=-180")
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_aggregated"] is True
    assert data["count"] == 1
    assert data["data"][0]["intensity"] == 5.0
    
    repo_mock.get_map_aggregations.assert_called_once()
    repo_mock.get_event_details.assert_not_called()

def test_map_data_detailed(override_dependencies):
    repo_mock = override_dependencies
    
    response = client.get("/api/v1/events/map?zoom=10.0&bbox_n=90&bbox_s=-90&bbox_e=180&bbox_w=-180")
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_aggregated"] is False
    assert data["count"] == 1
    assert data["data"][0]["global_event_id"] == 1
    
    repo_mock.get_event_details.assert_called_once()
    repo_mock.get_map_aggregations.assert_not_called()
