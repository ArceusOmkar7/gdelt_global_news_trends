"""Unit tests for the health router."""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

from backend.api.routers.health import _get_bq_client, _get_settings, _get_hot_repository

@pytest.fixture(autouse=True)
def override_dependencies():
    from unittest.mock import MagicMock
    from backend.infrastructure.config.settings import Settings
    from backend.infrastructure.data_access.bigquery_client import BigQueryClient
    from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository

    settings = Settings(gcp_project_id="test", bq_max_scan_bytes=1000)
    
    bq_mock = MagicMock(spec=BigQueryClient)
    bq_mock.health_check.return_value = {"connected": True, "project": "test", "dataset": "test"}
    
    hot_mock = MagicMock(spec=DuckDbRepository)
    hot_mock.health_check.return_value = {"path": "test", "available": True, "parquet_files": 1, "cutoff_days": 1}

    app.dependency_overrides[_get_settings] = lambda: settings
    app.dependency_overrides[_get_bq_client] = lambda: bq_mock
    app.dependency_overrides[_get_hot_repository] = lambda: hot_mock
    yield
    app.dependency_overrides.clear()

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "environment" in data
    assert "bigquery" in data
    assert "hot_tier" in data

def test_settings_endpoint():
    response = client.get("/api/v1/health/settings")
    assert response.status_code == 200
    data = response.json()
    assert "hot_tier_cutoff_days" in data
    assert "bq_max_scan_bytes" in data
