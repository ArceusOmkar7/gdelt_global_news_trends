"""Unit tests for the analytics router."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domain.models.event import EventCluster, ForecastPoint, ForecastResult, EventFilter
from backend.domain.ports.ports import IEventRepository
from backend.application.use_cases.cluster_events import ClusterEventsUseCase
from backend.application.use_cases.forecast_events import ForecastEventsUseCase

client = TestClient(app)

def _mock_cluster_use_case():
    mock = MagicMock(spec=ClusterEventsUseCase)
    mock.execute.return_value = [
        EventCluster(cluster_id=1, label="Test Cluster", event_count=10, top_country_codes=[], top_event_codes=[], event_ids=[])
    ]
    return mock

def _mock_forecast_use_case():
    mock = MagicMock(spec=ForecastEventsUseCase)
    mock.execute.return_value = ForecastResult(
        country_code="US",
        horizon_days=7,
        model_type="prophet",
        predictions=[ForecastPoint(date=date(2024, 1, 1), predicted_count=10.0)]
    )
    return mock

from backend.api.routers.analytics import _get_cluster_use_case, _get_forecast_use_case

@pytest.fixture
def override_dependencies():
    cluster_mock = _mock_cluster_use_case()
    forecast_mock = _mock_forecast_use_case()
    
    app.dependency_overrides[_get_cluster_use_case] = lambda: cluster_mock
    app.dependency_overrides[_get_forecast_use_case] = lambda: forecast_mock
    
    yield cluster_mock, forecast_mock
    
    app.dependency_overrides.clear()

def test_get_clusters(override_dependencies):
    cluster_mock, _ = override_dependencies
    
    response = client.get("/api/v1/analytics/clusters?n_clusters=5&limit=100")
    
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["data"][0]["cluster_id"] == 1
    assert data["data"][0]["label"] == "Test Cluster"
    
    cluster_mock.execute.assert_called_once()

def test_get_forecast(override_dependencies):
    _, forecast_mock = override_dependencies
    
    response = client.get("/api/v1/analytics/forecast/US?horizon_days=7")
    
    assert response.status_code == 200
    data = response.json()
    assert data["country_code"] == "US"
    assert data["horizon_days"] == 7
    assert len(data["predictions"]) == 1
    assert data["predictions"][0]["predicted_count"] == 10.0
    
    forecast_mock.execute.assert_called_once_with(horizon_days=7, country_code="US")
