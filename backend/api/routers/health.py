"""Health-check router — service diagnostics endpoint.

Provides comprehensive status information including BigQuery connectivity,
environment details, application version, and uptime.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.schemas.schemas import (
    BigQueryHealthDetail,
    HealthResponse,
    HotTierHealthDetail,
    RuntimeSettingsResponse,
)
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.data_access.bigquery_client import BigQueryClient
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository

router = APIRouter(tags=["health"])

# Set at app startup by main.py
_app_start_time: float = time.monotonic()
_bq_health_cache: dict | None = None
_bq_health_cache_at: float = 0.0
_bq_health_cache_lock = threading.Lock()
BQ_HEALTH_CACHE_TTL_SECONDS = 60.0

APP_VERSION = "0.1.0"


def _get_bq_client() -> BigQueryClient:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("BigQueryClient dependency not wired")


def _get_settings() -> Settings:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("Settings dependency not wired")


def _get_hot_repository() -> DuckDbRepository:
    """Dependency stub — overridden at app startup."""
    raise NotImplementedError("DuckDbRepository dependency not wired")


def set_app_start_time(t: float) -> None:
    """Called once from main.py at startup to record the boot timestamp."""
    global _app_start_time
    _app_start_time = t


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "Returns comprehensive service status including BigQuery connectivity, "
        "environment, version, and uptime."
    ),
)
def health_check(
    bq_client: Annotated[BigQueryClient, Depends(_get_bq_client)],
    settings: Annotated[Settings, Depends(_get_settings)],
    hot_repo: Annotated[DuckDbRepository, Depends(_get_hot_repository)],
) -> HealthResponse:
    global _bq_health_cache, _bq_health_cache_at

    now = time.monotonic()
    with _bq_health_cache_lock:
        cache_fresh = (
            _bq_health_cache is not None
            and (now - _bq_health_cache_at) < BQ_HEALTH_CACHE_TTL_SECONDS
        )
        if cache_fresh:
            bq_health = _bq_health_cache
        else:
            bq_health = bq_client.health_check()
            _bq_health_cache = bq_health
            _bq_health_cache_at = now

    hot_tier_path = Path(settings.hot_tier_path)
    parquet_files = list(hot_tier_path.glob("*.parquet")) if hot_tier_path.exists() else []
    
    ingestion_stats = hot_repo.get_ingestion_stats()

    bq_detail = BigQueryHealthDetail(
        connected=bq_health["connected"],
        project=bq_health["project"],
        dataset=bq_health["dataset"],
        latency_ms=bq_health.get("latency_ms"),
        error=bq_health.get("error"),
    )
    hot_tier_detail = HotTierHealthDetail(
        path=str(hot_tier_path),
        available=hot_tier_path.exists() and len(parquet_files) > 0,
        parquet_files=len(parquet_files),
        cutoff_days=settings.hot_tier_cutoff_days,
        total_rows=ingestion_stats["total_rows"],
        last_updated_at=ingestion_stats["last_updated_at"],
    )

    overall_status = "healthy" if (bq_detail.connected and hot_tier_detail.available) else "degraded"
    uptime = round(time.monotonic() - _app_start_time, 2)

    return HealthResponse(
        status=overall_status,
        environment=settings.environment,
        version=APP_VERSION,
        bigquery=bq_detail,
        hot_tier=hot_tier_detail,
        uptime_seconds=uptime,
    )


@router.get(
    "/health/settings",
    response_model=RuntimeSettingsResponse,
    summary="Runtime settings",
    description="Returns read-only backend runtime settings and ingestion cadences.",
)
def runtime_settings(
    settings: Annotated[Settings, Depends(_get_settings)],
) -> RuntimeSettingsResponse:
    return RuntimeSettingsResponse(
        hot_tier_cutoff_days=settings.hot_tier_cutoff_days,
        cold_tier_max_window_days=settings.cold_tier_max_window_days,
        cold_tier_monthly_query_limit=settings.cold_tier_monthly_query_limit,
        bq_max_scan_bytes=settings.bq_max_scan_bytes,
        default_lookback_days=settings.default_lookback_days,
        default_query_limit=settings.default_query_limit,
        realtime_fetch_interval_minutes=15,
        daily_batch_cron_utc="0 2 * * *",
        nightly_ai_cron_utc="0 3 * * *",
    )
