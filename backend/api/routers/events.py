"""Events router — HTTP endpoints for GDELT event data.

Zero business logic.  Maps HTTP request parameters to domain filters,
delegates to the use case, and maps domain models to response schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    EventCountListResponse,
    EventCountResponse,
    EventFilterRequest,
    EventListResponse,
    EventResponse,
)
from backend.application.use_cases.get_events import GetEventsUseCase
from backend.domain.models.event import EventFilter

router = APIRouter(prefix="/events", tags=["events"])


def _get_use_case() -> GetEventsUseCase:
    """Dependency stub — overridden at app startup via dependency_overrides."""
    raise NotImplementedError("GetEventsUseCase dependency not wired")


@router.get(
    "",
    response_model=EventListResponse,
    summary="List GDELT events",
    description=(
        "Retrieve GDELT events matching optional filters. "
        "Defaults to the last 7 days with a 1 000-row limit."
    ),
)
def list_events(
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    start_date: date | None = Query(default=None, description="Inclusive start date"),
    end_date: date | None = Query(default=None, description="Inclusive end date"),
    country_code: str | None = Query(default=None, max_length=3, description="Country code"),
    event_root_code: str | None = Query(default=None, max_length=2, description="CAMEO root code"),
    limit: int = Query(default=1000, ge=1, le=100_000, description="Row limit"),
) -> EventListResponse:
    filters = EventFilter(
        start_date=start_date,
        end_date=end_date,
        country_code=country_code,
        event_root_code=event_root_code,
        limit=limit,
    )
    events = use_case.execute(filters)
    data = [EventResponse.model_validate(e.model_dump()) for e in events]
    return EventListResponse(count=len(data), data=data)


@router.get(
    "/region/{country_code}",
    response_model=EventListResponse,
    summary="Events by region",
    description="Retrieve events for a specific country/region.",
)
def events_by_region(
    country_code: str,
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=100_000),
) -> EventListResponse:
    events = use_case.get_by_region(
        country_code=country_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    data = [EventResponse.model_validate(e.model_dump()) for e in events]
    return EventListResponse(count=len(data), data=data)


@router.get(
    "/counts/{country_code}",
    response_model=EventCountListResponse,
    summary="Daily event counts by country",
    description="Get daily-aggregated event counts for time-series charting.",
)
def event_counts_by_country(
    country_code: str,
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> EventCountListResponse:
    counts = use_case.get_daily_counts(
        country_code=country_code,
        start_date=start_date,
        end_date=end_date,
    )
    data = [EventCountResponse.model_validate(c.model_dump()) for c in counts]
    return EventCountListResponse(count=len(data), data=data)


@router.get(
    "/counts",
    response_model=EventCountListResponse,
    summary="Global daily event counts",
    description="Get daily-aggregated event counts globally (no country filter).",
)
def event_counts_global(
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> EventCountListResponse:
    counts = use_case.get_daily_counts(
        country_code=None,
        start_date=start_date,
        end_date=end_date,
    )
    data = [EventCountResponse.model_validate(c.model_dump()) for c in counts]
    return EventCountListResponse(count=len(data), data=data)
