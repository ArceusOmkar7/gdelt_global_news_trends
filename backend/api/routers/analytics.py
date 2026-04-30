"""Analytics router — HTTP endpoints for clustering and forecasting.

Maps HTTP requests to application use cases involving event clustering 
and time-series forecasting.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    AnalyticsDeltaResponse,
    AnomalyResponse,
    BriefingsResponse,
    ClusterListResponse,
    CountryBriefingEntry,
    EventClusterResponse,
    EventFilterRequest,
    ForecastPointResponse,
    ForecastResponse,
    LiveStreamChannelResponse,
    LiveStreamGroupResponse,
    SpikeAlertEntry,
    SpikeAlertResponse,
)
from backend.application.use_cases.cluster_events import ClusterEventsUseCase
from backend.application.use_cases.forecast_events import ForecastEventsUseCase
from backend.domain.models.event import EventFilter
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository
from backend.infrastructure.config.settings import settings
from backend.infrastructure.services.live_stream_service import live_stream_service

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
    event_root_codes: str | None = Query(default=None),
    geo_country: str | None = Query(default=None),
    geo_state: str | None = Query(default=None),
    geo_city: str | None = Query(default=None),
    theme_category: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000, description="Max rows to query"),
) -> ClusterListResponse:
    codes = [c.strip() for c in event_root_codes.split(",") if c.strip()] if event_root_codes else None
    filters = EventFilter(
        start_date=start_date,
        end_date=end_date,
        country_code=country_code,
        event_root_codes=codes,
        geo_country=geo_country,
        geo_state=geo_state,
        geo_city=geo_city,
        theme_category=theme_category,
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


_spike_cache: list[SpikeAlertEntry] | None = None
_spike_cache_at: float = 0.0
_spike_cache_lock = threading.Lock()
SPIKE_CACHE_TTL = 900.0  # 15 minutes


@router.get(
    "/spikes",
    response_model=SpikeAlertResponse,
    summary="Activity spike alerts",
    description="Identifies countries with >= 2.0x event spike vs 7-day average.",
)
def get_activity_spikes(
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
) -> SpikeAlertResponse:
    global _spike_cache, _spike_cache_at

    now = time.monotonic()
    with _spike_cache_lock:
        if _spike_cache is not None and (now - _spike_cache_at) < SPIKE_CACHE_TTL:
            return SpikeAlertResponse(count=len(_spike_cache), data=_spike_cache)

        spikes = hot_repo.get_activity_spikes()
        # Map to schema
        data = [SpikeAlertEntry.model_validate(s) for s in spikes]
        _spike_cache = data
        _spike_cache_at = now
        return SpikeAlertResponse(count=len(data), data=data)


@router.get(
    "/anomalies",
    response_model=AnomalyResponse,
    summary="Regional anomalies",
    description="Returns pre-computed IsolationForest anomaly detection results.",
)
def get_regional_anomalies(
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
) -> AnomalyResponse:
    anomalies = hot_repo.get_anomalies()
    return AnomalyResponse(data=anomalies)


@router.get(
    "/briefings",
    response_model=BriefingsResponse,
    summary="Nightly country briefings",
    description="Returns pre-computed nightly briefing cache keyed by country code.",
)
def get_nightly_briefings(
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
) -> BriefingsResponse:
    briefings = hot_repo.get_briefings()
    data = {
        code: CountryBriefingEntry.model_validate(payload)
        for code, payload in briefings.items()
    }
    return BriefingsResponse(count=len(data), data=data)


@router.get("/theme-categories")
def get_theme_categories(
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
):
    """Returns pre-computed theme category event counts from nightly cache."""
    cache_path = Path(settings.cache_path) / "theme_categories.json"
    if not cache_path.exists():
        return {"data": {}}
    import json
    return {"data": json.loads(cache_path.read_text())}


@router.get(
    "/live-streams",
    response_model=LiveStreamGroupResponse,
    summary="Resolve live stream embeds",
    description="Returns cached live stream embed metadata for a country group.",
)
def get_live_streams(
    country_code: str | None = Query(default=None, description="Country code (e.g., US, IN)."),
) -> LiveStreamGroupResponse:
    data = live_stream_service.get_group(country_code)
    channels = [LiveStreamChannelResponse.model_validate(item) for item in data["channels"]]
    return LiveStreamGroupResponse(
        group_key=data["group_key"],
        label=data["label"],
        channels=channels,
    )


@router.get(
    "/live-streams/refresh",
    response_model=LiveStreamChannelResponse,
    summary="Refresh a live stream embed",
    description="Forces a refresh for a single channel when an embed fails.",
)
def refresh_live_stream(
    channel_id: str = Query(..., description="YouTube channel ID."),
) -> LiveStreamChannelResponse:
    data = live_stream_service.refresh_channel(channel_id)
    return LiveStreamChannelResponse.model_validate(data)
