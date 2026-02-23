"""Use case — time-series forecasting of conflict events."""

from __future__ import annotations

import structlog

from backend.domain.models.event import EventFilter, ForecastResult
from backend.domain.ports.ports import IEventRepository, IForecastingService

logger = structlog.get_logger(__name__)


class ForecastEventsUseCase:
    """Application-layer orchestrator for conflict forecasting.
    
    Validates horizon constraints, fetches historical daily counts
    from the repository, and delegates prediction to the domain service.
    """

    def __init__(
        self,
        repository: IEventRepository,
        forecasting_service: IForecastingService,
    ) -> None:
        self._repository = repository
        self._forecasting_service = forecasting_service

    def execute(
        self,
        horizon_days: int = 7,
        country_code: str | None = None,
    ) -> ForecastResult:
        """Fetch historical counts and forecast future volume.
        
        Args:
            horizon_days: Days into the future to predict (clamped to 1-90).
            country_code: Optional ISO country filter.
            
        Returns:
            Domain `ForecastResult` object containing the prediction curve.
        """
        # 1. Validate application constraints
        horizon_days = max(1, min(horizon_days, 90))
        
        logger.info(
            "forecast_events_execute",
            horizon_days=horizon_days,
            country_code=country_code,
        )

        # 2. Fetch historical training data (default lookback is usually 7-30 days,
        # but for forecasting we want slightly more history. The repository
        # lets us pass None dates to use defaults, but let's be explicit to get
        # enough training data for Prophet).
        import datetime
        end_date = datetime.date.today()
        # Prophet works best with >3 months of daily data for strong seasonality,
        # but for this prototype 30 days is acceptable to execute quickly on local HW.
        start_date = end_date - datetime.timedelta(days=90)
        
        filters = EventFilter(
            start_date=start_date,
            end_date=end_date,
        )
        
        historical_counts = self._repository.get_event_counts_by_date(
            country_code=country_code,
            filters=filters,
        )

        # 3. Delegate to domain service
        result = self._forecasting_service.forecast(
            historical_counts=historical_counts,
            horizon_days=horizon_days,
            country_code=country_code,
        )
        
        logger.info(
            "forecast_events_success",
            training_days=len(historical_counts),
            predicted_days=len(result.predictions),
        )
        return result
