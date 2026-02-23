"""Unit tests for the Prophet Forecasting Service."""

from datetime import date, timedelta
from backend.domain.models.event import EventCountByDate
from backend.domain.services.forecasting_service import ForecastingService

def _make_count(dt: date, count: int) -> EventCountByDate:
    return EventCountByDate(date=dt, count=count)

class TestForecastingService:
    def setup_method(self):
        self.service = ForecastingService()
        
        # Create 14 days of dummy historical data
        start = date(2024, 1, 1)
        self.history = [
            _make_count(start + timedelta(days=i), 100 + (i * 10)) 
            for i in range(14)
        ]

    def test_forecast_returns_correct_horizon(self):
        horizon = 5
        res = self.service.forecast(self.history, horizon_days=horizon, country_code="US")
        
        assert res.horizon_days == horizon
        assert res.country_code == "US"
        assert len(res.predictions) == horizon
        
        # The first prediction date should be right after the last historical date
        last_historical = self.history[-1].date
        assert res.predictions[0].date == last_historical + timedelta(days=1)
        assert res.predictions[-1].date == last_historical + timedelta(days=horizon)

    def test_forecast_insufficient_data_fallback(self):
        # Prophet needs >2 data points, passing 1 should trigger the fallback
        single_point = [_make_count(date(2024, 1, 1), 500)]
        
        res = self.service.forecast(single_point, horizon_days=3)
        
        assert res.model_type == "naive_fallback"
        assert len(res.predictions) == 3
        # Fallback just repeats the last known value
        assert all(p.predicted_count == 500 for p in res.predictions)

    def test_forecast_empty_history(self):
        res = self.service.forecast([], horizon_days=2)
        
        assert res.model_type == "naive_fallback"
        assert len(res.predictions) == 2
        assert all(p.predicted_count == 0.0 for p in res.predictions)
        
    def test_forecast_clamps_negative_predictions(self):
        # Create a steep downward trend that would force Prophet below 0
        steep_drop = [
            _make_count(date(2024, 1, i), 1000 - (i * 150))
            for i in range(1, 10)
        ]
        
        res = self.service.forecast(steep_drop, horizon_days=5)
        
        # Verify predictions never drop below zero
        assert all(p.predicted_count >= 0.0 for p in res.predictions)
