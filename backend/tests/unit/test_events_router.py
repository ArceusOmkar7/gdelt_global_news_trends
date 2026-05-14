"""Unit tests for the events router."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domain.models.event import Event, EventAnalysis, ExtractedArticle
from backend.application.use_cases.get_events import GetEventsUseCase
from backend.application.use_cases.analyze_event import AnalyzeEventUseCase

client = TestClient(app)

def _mock_get_events():
    mock = MagicMock(spec=GetEventsUseCase)
    mock.execute.return_value = [
        Event(global_event_id=1, sql_date=date(2024, 1, 1), source_url="http://test.com")
    ]
    return mock

def _mock_analyze_event():
    mock = MagicMock(spec=AnalyzeEventUseCase)
    mock.execute.return_value = EventAnalysis(
        summary="Test analysis",
        sentiment="Positive",
        entities=[],
        themes=[],
        confidence=0.9,
        images=[],
        embeds=[]
    )
    return mock

from backend.api.routers.events import _get_use_case, _get_analyze_use_case

@pytest.fixture
def override_dependencies():
    get_mock = _mock_get_events()
    analyze_mock = _mock_analyze_event()
    
    app.dependency_overrides[_get_use_case] = lambda: get_mock
    app.dependency_overrides[_get_analyze_use_case] = lambda: analyze_mock
    
    yield get_mock, analyze_mock
    
    app.dependency_overrides.clear()

def test_get_events(override_dependencies):
    get_mock, _ = override_dependencies
    
    response = client.get("/api/v1/events?limit=10")
    
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["data"][0]["global_event_id"] == 1
    
    get_mock.execute.assert_called_once()

@pytest.mark.asyncio
def test_analyze_event_api(override_dependencies):
    _, analyze_mock = override_dependencies
    
    response = client.get("/api/v1/events/1/analyze")
    
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test analysis"
    assert data["sentiment"] == "Positive"
    
    analyze_mock.execute.assert_called_once_with(1)
