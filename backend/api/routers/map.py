"""Map router — HTTP endpoints for geospatial event data."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    MapAggregationResponse,
    MapDataResponse,
    MapEventDetailResponse,
)
from backend.application.use_cases.get_events import GetEventsUseCase

router = APIRouter(prefix="/events/map", tags=["map"])

# ---------------------------------------------------------------------------
# Simple in-process response cache
# ---------------------------------------------------------------------------
# Keyed by a hash of (bbox, zoom, dates, event_root_code).
# TTL: 60s for aggregated view, 30s for detail view.
# This is process-local and resets on restart — that's fine, it's only a
# performance optimisation, not a correctness dependency.

_map_cache: dict[str, tuple[float, MapDataResponse]] = {}
_AGG_TTL   = 60.0   # seconds — aggregated world/region view
_DETAIL_TTL = 30.0  # seconds — detailed event view


def _cache_key(
    bbox_n: float, bbox_s: float, bbox_e: float, bbox_w: float,
    zoom: float, start_date: date | None, end_date: date | None,
    event_root_code: str | None,
) -> str:
    payload = json.dumps(
        [round(bbox_n, 2), round(bbox_s, 2), round(bbox_e, 2), round(bbox_w, 2),
         round(zoom, 1),
         str(start_date), str(end_date), event_root_code],
        sort_keys=True,
    )
    return hashlib.md5(payload.encode()).hexdigest()


def _get_use_case() -> GetEventsUseCase:
    raise NotImplementedError("GetEventsUseCase dependency not wired")


@router.get("", response_model=MapDataResponse)
def get_map_data(
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    bbox_n: float = Query(...),
    bbox_s: float = Query(...),
    bbox_e: float = Query(...),
    bbox_w: float = Query(...),
    zoom: float = Query(..., ge=0, le=22),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    event_root_code: str | None = Query(default=None, max_length=2),
    limit: int = Query(default=10000, ge=1, le=100_000),
) -> MapDataResponse:
    is_aggregated_mode = zoom < 9.0
    ttl = _AGG_TTL if is_aggregated_mode else _DETAIL_TTL

    key = _cache_key(bbox_n, bbox_s, bbox_e, bbox_w, zoom, start_date, end_date, event_root_code)
    cached = _map_cache.get(key)
    if cached is not None:
        cached_at, response = cached
        if time.monotonic() - cached_at < ttl:
            return response

    # --- cache miss: run the actual query ---
    if is_aggregated_mode:
        if zoom >= 7:
            grid_precision = 4
        elif zoom >= 5:
            grid_precision = 3
        elif zoom >= 3:
            grid_precision = 2
        elif zoom >= 1:
            grid_precision = 1
        else:
            grid_precision = 0

        aggregations = use_case.get_map_aggregations(
            bbox_n=bbox_n, bbox_s=bbox_s, bbox_e=bbox_e, bbox_w=bbox_w,
            start_date=start_date, end_date=end_date,
            event_root_code=event_root_code,
            grid_precision=grid_precision, limit=limit,
        )
        data = [MapAggregationResponse.model_validate(agg.model_dump()) for agg in aggregations]
        response = MapDataResponse(zoom=zoom, is_aggregated=True, count=len(data), data=data)
    else:
        details = use_case.get_map_event_details(
            bbox_n=bbox_n, bbox_s=bbox_s, bbox_e=bbox_e, bbox_w=bbox_w,
            start_date=start_date, end_date=end_date,
            event_root_code=event_root_code, limit=limit,
        )
        data = [MapEventDetailResponse.model_validate(det.model_dump()) for det in details]
        response = MapDataResponse(zoom=zoom, is_aggregated=False, count=len(data), data=data)

    _map_cache[key] = (time.monotonic(), response)

    # Evict entries older than 5× the longest TTL to prevent unbounded growth
    cutoff = time.monotonic() - (_AGG_TTL * 5)
    expired = [k for k, (t, _) in _map_cache.items() if t < cutoff]
    for k in expired:
        _map_cache.pop(k, None)

    return response