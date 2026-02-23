"""Map router — HTTP endpoints for geospatial event data.

Handles semantic zoom by switching between aggregated grid views and 
individual event detail views based on zoom level.
"""

from __future__ import annotations

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


def _get_use_case() -> GetEventsUseCase:
    """Dependency stub — overridden at app startup via dependency_overrides."""
    raise NotImplementedError("GetEventsUseCase dependency not wired")


@router.get(
    "",
    response_model=MapDataResponse,
    summary="Get geospatial event data",
    description=(
        "Returns geographically aggregated heat intensities (zoom < 9) "
        "or individual event coordinates and metadata (zoom >= 9)."
    ),
)
def get_map_data(
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    bbox_n: float = Query(..., description="North latitude bound"),
    bbox_s: float = Query(..., description="South latitude bound"),
    bbox_e: float = Query(..., description="East longitude bound"),
    bbox_w: float = Query(..., description="West longitude bound"),
    zoom: int = Query(..., ge=0, le=22, description="Zoom level"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    event_root_code: str | None = Query(default=None, max_length=2),
    limit: int = Query(default=10000, ge=1, le=100_000, description="Row limit"),
) -> MapDataResponse:
    if zoom < 9:
        # Level 1/2: Aggregated view
        # Finer grid as we zoom in
        if zoom >= 7:
            grid_precision = 2
        elif zoom >= 5:
            grid_precision = 1
        else:
            grid_precision = 0
        
        aggregations = use_case.get_map_aggregations(
            bbox_n=bbox_n,
            bbox_s=bbox_s,
            bbox_e=bbox_e,
            bbox_w=bbox_w,
            start_date=start_date,
            end_date=end_date,
            event_root_code=event_root_code,
            grid_precision=grid_precision,
            limit=limit,
        )
        data = [
            MapAggregationResponse.model_validate(agg.model_dump())
            for agg in aggregations
        ]
        return MapDataResponse(
            zoom=zoom,
            is_aggregated=True,
            count=len(data),
            data=data,
        )
    else:
        # Level 2/3: Detailed view
        details = use_case.get_map_event_details(
            bbox_n=bbox_n,
            bbox_s=bbox_s,
            bbox_e=bbox_e,
            bbox_w=bbox_w,
            start_date=start_date,
            end_date=end_date,
            event_root_code=event_root_code,
            limit=limit,
        )
        data = [
            MapEventDetailResponse.model_validate(det.model_dump())
            for det in details
        ]
        return MapDataResponse(
            zoom=zoom,
            is_aggregated=False,
            count=len(data),
            data=data,
        )
