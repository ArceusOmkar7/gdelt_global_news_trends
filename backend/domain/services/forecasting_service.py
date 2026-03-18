"""Forecasting service — time-series prediction using Prophet.

Uses Facebook Prophet to forecast GDELT event volumes. Prophet is excellent
for daily data with seasonality and missing observations.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from backend.domain.models.event import EventCountByDate, ForecastPoint, ForecastResult
from backend.domain.ports.ports import IForecastingService

logger = logging.getLogger(__name__)


class ForecastingService(IForecastingService):
    """Implementation of IForecastingService using Prophet."""

    def forecast(
        self,
        historical_counts: list[EventCountByDate],
        horizon_days: int,
        country_code: str | None = None,
    ) -> ForecastResult:
        """Produce a forecast from historical event counts."""
        # 1. Prepare historical summary
        total_historical_events = sum(c.count for c in historical_counts)
        days_of_data = len(historical_counts)
        summary = {
            "training_days": days_of_data,
            "total_historical_events": total_historical_events,
        }

        # 2. Handle edge cases (empty or insufficient data)
        # Prophet typcially needs at least two non-NaN rows to fit.
        if days_of_data < 2:
            logger.warning(
                "Insufficient data for Prophet forecasting (%d days)", days_of_data
            )
            return self._build_fallback_forecast(
                historical_counts, horizon_days, country_code, summary
            )

        # 3. Convert domain models into a Pandas DataFrame for Prophet
        # Prophet expects columns 'ds' (datestamp) and 'y' (numeric value)
        # Import heavy ML deps lazily to keep API startup fast.
        import pandas as pd
        from prophet import Prophet

        data = [
            {"ds": count.date, "y": count.count}
            for count in historical_counts
        ]
        df = pd.DataFrame(data)

        # 4. Train the Prophet model
        # Disabling daily seasonality since our data grain is already daily
        # Disabling weekly/yearly if we have too little data to support it
        m = Prophet(
            daily_seasonality=False,
            weekly_seasonality=days_of_data >= 7,
            yearly_seasonality=days_of_data >= 365,
        )
        try:
            m.fit(df)
        except Exception as e:
            logger.error("Prophet model fitting failed: %s", e)
            return self._build_fallback_forecast(
                historical_counts, horizon_days, country_code, summary
            )

        # 5. Create future dataframe and predict
        future = m.make_future_dataframe(periods=horizon_days, freq="D")
        forecast_df = m.predict(future)

        # 6. Extract only the future predictions (drop the training period)
        # Using tail is safer than date comparisons which can throw TypeErrors
        future_forecast = forecast_df.tail(horizon_days)

        # 7. Map back to domain models
        predictions = []
        for _, row in future_forecast.iterrows():
            # Prophet output can dip below zero for event counts, clamp at 0
            pred_count = max(0.0, float(row["yhat"]))
            lower_bound = max(0.0, float(row["yhat_lower"]))
            upper_bound = max(0.0, float(row["yhat_upper"]))

            predictions.append(
                ForecastPoint(
                    date=row["ds"].date(),
                    predicted_count=pred_count,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                )
            )

        return ForecastResult(
            country_code=country_code,
            horizon_days=horizon_days,
            model_type="prophet",
            historical_summary=summary,
            predictions=predictions,
        )

    def _build_fallback_forecast(
        self,
        historical_counts: list[EventCountByDate],
        horizon_days: int,
        country_code: str | None,
        summary: dict,
    ) -> ForecastResult:
        """Create a naive flatline forecast when modelling fails or data is missing."""
        predictions = []
        
        # If completely empty, assume tomorrow is 0
        if not historical_counts:
            import datetime
            last_date = datetime.date.today()
            last_count = 0.0
        else:
            last_date = historical_counts[-1].date
            last_count = float(historical_counts[-1].count)

        for i in range(1, horizon_days + 1):
            next_date = last_date + timedelta(days=i)
            predictions.append(
                ForecastPoint(
                    date=next_date,
                    predicted_count=last_count,
                    lower_bound=last_count,
                    upper_bound=last_count,
                )
            )

        return ForecastResult(
            country_code=country_code,
            horizon_days=horizon_days,
            model_type="naive_fallback",
            historical_summary=summary,
            predictions=predictions,
        )
