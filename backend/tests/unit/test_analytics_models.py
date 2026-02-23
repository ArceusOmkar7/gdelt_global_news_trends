"""Unit tests for the new Phase 2 domain models and response schemas."""

from datetime import date
import pytest

from backend.domain.models.event import EventCluster, ForecastPoint, ForecastResult


class TestEventCluster:
    def test_create_valid_cluster(self):
        cluster = EventCluster(
            cluster_id=0,
            label="US - Event 01",
            event_count=50,
            avg_goldstein_scale=2.5,
            top_country_codes=["US", "GB"],
            top_event_codes=["01", "14"],
            event_ids=[1, 2, 3]
        )
        assert cluster.cluster_id == 0
        assert cluster.label == "US - Event 01"
        assert cluster.event_count == 50

    def test_cluster_is_frozen(self):
        cluster = EventCluster(cluster_id=1, label="Test", event_count=10)
        with pytest.raises(Exception):
            cluster.event_count = 20  # type: ignore


class TestForecastModels:
    def test_create_forecast_point(self):
        pt = ForecastPoint(
            date=date(2024, 2, 1),
            predicted_count=100.5,
            lower_bound=90.0,
            upper_bound=110.0
        )
        assert pt.predicted_count == 100.5
        
    def test_create_forecast_result(self):
        res = ForecastResult(
            country_code="US",
            horizon_days=7,
            model_type="prophet",
            historical_summary={"training_days": 30},
            predictions=[
                ForecastPoint(date=date(2024, 2, 1), predicted_count=10.0)
            ]
        )
        assert res.country_code == "US"
        assert len(res.predictions) == 1
