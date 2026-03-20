"""Events router — HTTP endpoints for GDELT event data.

Zero business logic.  Maps HTTP request parameters to domain filters,
delegates to the use case, and maps domain models to response schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    EventAnalysisResponse,
    EventCountListResponse,
    EventCountResponse,
    EventFilterRequest,
    EventListResponse,
    EventResponse,
)
from backend.application.use_cases.analyze_event import AnalyzeEventUseCase
from backend.application.use_cases.get_events import GetEventsUseCase
from backend.domain.models.event import EventFilter

router = APIRouter(prefix="/events", tags=["events"])


def _get_use_case() -> GetEventsUseCase:
    """Dependency stub — overridden at app startup via dependency_overrides."""
    raise NotImplementedError("GetEventsUseCase dependency not wired")


def _get_analyze_use_case() -> AnalyzeEventUseCase:
    """Dependency stub."""
    raise NotImplementedError("AnalyzeEventUseCase dependency not wired")


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
    "/region/{country_code}/stats",
    summary="Regional intelligence stats",
    description="Get top themes and entities for a specific region.",
)
def regional_stats(
    country_code: str,
    use_case: Annotated[GetEventsUseCase, Depends(_get_use_case)],
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    """Returns top themes, persons, and organizations for a country."""
    # This logic would ideally be in a service/use case, but for now we'll 
    # use the use_case to get events and aggregate them here for brevity.
    events = use_case.get_by_region(
        country_code=country_code,
        start_date=start_date,
        end_date=end_date,
        limit=2000, # Use a larger sample for better stats
    )
    
    from collections import Counter
    themes = Counter()
    persons = Counter()
    orgs = Counter()
    
    for e in events:
        themes.update(e.themes)
        persons.update(e.persons)
        orgs.update(e.organizations)
        
    return {
        "country_code": country_code.upper(),
        "top_themes": [{"name": k, "count": v} for k, v in themes.most_common(10)],
        "top_persons": [{"name": k, "count": v} for k, v in persons.most_common(10)],
        "top_organizations": [{"name": k, "count": v} for k, v in orgs.most_common(10)],
    }


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


@router.get(
    "/{event_id}/analyze",
    response_model=EventAnalysisResponse,
    summary="Analyze event via LLM",
    description=(
        "Performs on-demand deep intelligence analysis for a single event. "
        "Scrapes the source article and uses an LLM to generate insights."
    ),
)
async def analyze_event(
    event_id: int,
    use_case: Annotated[AnalyzeEventUseCase, Depends(_get_analyze_use_case)],
) -> EventAnalysisResponse:
    analysis = await use_case.execute(event_id)
    return EventAnalysisResponse.model_validate(analysis.model_dump())
