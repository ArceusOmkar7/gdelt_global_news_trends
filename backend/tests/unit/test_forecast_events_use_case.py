"""Unit tests for ForecastEventsUseCase."""

from datetime import date
from unittest.mock import MagicMock

from backend.application.use_cases.forecast_events import ForecastEventsUseCase
from backend.domain.models.event import EventCountByDate, ForecastPoint, ForecastResult
from backend.domain.ports.ports import IEventRepository, IForecastingService


class TestForecastEventsUseCase:
    def setup_method(self):
        self.mock_repo = MagicMock(spec=IEventRepository)
        self.mock_service = MagicMock(spec=IForecastingService)
        self.use_case = ForecastEventsUseCase(
            repository=self.mock_repo,
            forecasting_service=self.mock_service
        )

    def test_execute_delegates_to_service(self):
        history = [EventCountByDate(date=date(2024, 1, 1), count=10)]
        self.mock_repo.get_event_counts_by_date.return_value = history
        
        mock_result = ForecastResult(
            country_code="US",
            horizon_days=7,
            model_type="prophet",
            predictions=[ForecastPoint(date=date(2024, 1, 2), predicted_count=5.0)]
        )
        self.mock_service.forecast.return_value = mock_result

        result = self.use_case.execute(horizon_days=7, country_code="US")

        # Verify repository was called with correct context
        self.mock_repo.get_event_counts_by_date.assert_called_once()
        repo_args = self.mock_repo.get_event_counts_by_date.call_args
        assert repo_args.kwargs["country_code"] == "US"
        assert repo_args.kwargs["filters"].start_date is not None

        # Verify service was called correctly
        self.mock_service.forecast.assert_called_once_with(
            historical_counts=history,
            horizon_days=7,
            country_code="US"
        )
        
        assert result == mock_result

    def test_execute_clamps_horizon_days(self):
        self.mock_repo.get_event_counts_by_date.return_value = []
        
        # Requesting 900 days should clamp to 90
        self.use_case.execute(horizon_days=900)
        call_args = self.mock_service.forecast.call_args
        assert call_args.kwargs["horizon_days"] == 90
        
        # Requesting 0 days should clamp to 1
        self.use_case.execute(horizon_days=0)
        call_args2 = self.mock_service.forecast.call_args
        assert call_args2.kwargs["horizon_days"] == 1
