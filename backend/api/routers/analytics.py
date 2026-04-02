"""Analytics router — HTTP endpoints for clustering and forecasting.

Maps HTTP requests to application use cases involving event clustering 
and time-series forecasting.
"""

from __future__ import annotations

import time
import threading
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    AnalyticsDeltaResponse,
    ClusterListResponse,
    EventClusterResponse,
    EventFilterRequest,
    ForecastPointResponse,
    ForecastResponse,
)
from backend.application.use_cases.cluster_events import ClusterEventsUseCase
from backend.application.use_cases.forecast_events import ForecastEventsUseCase
from backend.domain.models.event import EventFilter
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_cluster_use_case() -> ClusterEventsUseCase:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("ClusterEventsUseCase dependency not wired")


def _get_forecast_use_case() -> ForecastEventsUseCase:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("ForecastEventsUseCase dependency not wired")


def _get_hot_repository() -> DuckDbRepository:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("DuckDbRepository dependency not wired")


_delta_cache: dict | None = None
_delta_cache_at: float = 0.0
_delta_cache_lock = threading.Lock()
DELTA_CACHE_TTL = 3600.0


@router.get(
    "/clusters",
    response_model=ClusterListResponse,
    summary="Cluster GDELT events",
    description="Groups events into semantic clusters (prototype via TF-IDF).",
)
def get_event_clusters(
    use_case: Annotated[ClusterEventsUseCase, Depends(_get_cluster_use_case)],
    n_clusters: int = Query(default=5, ge=2, le=20, description="Number of clusters"),
    start_date: date | None = Query(default=None, description="Inclusive start date"),
    end_date: date | None = Query(default=None, description="Inclusive end date"),
    country_code: str | None = Query(default=None, max_length=3),
    event_root_code: str | None = Query(default=None, max_length=2),
    limit: int = Query(default=1000, ge=1, le=10000, description="Max rows to query"),
) -> ClusterListResponse:
    filters = EventFilter(
        start_date=start_date,
        end_date=end_date,
        country_code=country_code,
        event_root_code=event_root_code,
        limit=limit,
    )
    clusters = use_case.execute(filters=filters, n_clusters=n_clusters)
    
    # Map domain models to response schemas
    data = [EventClusterResponse.model_validate(c.model_dump()) for c in clusters]
    return ClusterListResponse(count=len(data), data=data)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Global conflict forecast",
    description="Forecasts future global event volumes.",
)
def get_global_forecast(
    use_case: Annotated[ForecastEventsUseCase, Depends(_get_forecast_use_case)],
    horizon_days: int = Query(default=7, ge=1, le=90, description="Days to predict"),
) -> ForecastResponse:
    result = use_case.execute(horizon_days=horizon_days, country_code=None)
    return ForecastResponse.model_validate(result.model_dump())


@router.get(
    "/forecast/{country_code}",
    response_model=ForecastResponse,
    summary="Regional conflict forecast",
    description="Forecasts future event volumes for a specific country.",
)
def get_regional_forecast(
    country_code: str,
    use_case: Annotated[ForecastEventsUseCase, Depends(_get_forecast_use_case)],
    horizon_days: int = Query(default=7, ge=1, le=90, description="Days to predict"),
) -> ForecastResponse:
    result = use_case.execute(horizon_days=horizon_days, country_code=country_code)
    return ForecastResponse.model_validate(result.model_dump())


@router.get(
    "/deltas",
    response_model=AnalyticsDeltaResponse,
    summary="Week-over-week deltas",
    description="Calculates WoW changes for top 20 countries.",
)
def get_analytics_deltas(
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
) -> AnalyticsDeltaResponse:
    global _delta_cache, _delta_cache_at

    now = time.monotonic()
    with _delta_cache_lock:
        if _delta_cache is not None and (now - _delta_cache_at) < DELTA_CACHE_TTL:
            return AnalyticsDeltaResponse(data=_delta_cache)

        deltas = hot_repo.get_analytics_deltas()
        _delta_cache = deltas
        _delta_cache_at = now
        return AnalyticsDeltaResponse(data=deltas)
