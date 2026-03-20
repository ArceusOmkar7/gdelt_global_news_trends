"""Events router — HTTP endpoints for GDELT event data.

Zero business logic.  Maps HTTP request parameters to domain filters,
delegates to the use case, and maps domain models to response schemas.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
import threading
import time as _time

from fastapi import APIRouter, Depends, Query

from backend.api.schemas.schemas import (
    EventAnalysisResponse,
    EventCountListResponse,
    EventCountResponse,
    EventFilterRequest,
    EventListResponse,
    EventResponse,
    RiskScoreResponse,
    GlobalPulseResponse, 
    ThreatCountryEntry, 
    TopThreatCountriesResponse
)
from backend.application.use_cases.analyze_event import AnalyzeEventUseCase
from backend.application.use_cases.get_events import GetEventsUseCase
from backend.domain.models.event import EventFilter
from backend.infrastructure.config.settings import settings
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository, compute_risk_score

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
    "/region/{country_code}/risk-score",
    response_model=RiskScoreResponse,
    summary="Country risk score",
    description="Compute a country risk score from hot-tier DuckDB data.",
)
def country_risk_score(
    country_code: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> RiskScoreResponse:
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=7))

    repository = DuckDbRepository(settings)
    metrics = repository.get_risk_score(
        country_code=country_code,
        start_date=start,
        end_date=end,
    )
    score = compute_risk_score(
        metrics["conflict_ratio"],
        metrics["avg_goldstein"],
        metrics["avg_tone"],
    )

    return RiskScoreResponse(
        score=score,
        trend="stable",
        conflict_ratio=metrics["conflict_ratio"],
        avg_goldstein=metrics["avg_goldstein"],
        avg_tone=metrics["avg_tone"],
        total_events=metrics["total_events"],
    )


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

# ---------------------------------------------------------------------------
# In-process TTL caches (process-local, resets on restart — intentional)
# ---------------------------------------------------------------------------
_pulse_cache: dict = {}
_pulse_cache_lock = threading.Lock()
_PULSE_TTL = 60.0   # 60 s
 
_threat_cache: dict = {}
_threat_cache_lock = threading.Lock()
_THREAT_TTL = 120.0  # 2 min
 
 
# ---------------------------------------------------------------------------
# 15.1 — Global Pulse endpoint
# ---------------------------------------------------------------------------
 
@router.get(
    "/global-pulse",
    response_model=GlobalPulseResponse,
    summary="Global pulse stats",
    description=(
        "Returns live aggregate stats across all recent events: "
        "total count, most-active and most-hostile countries, "
        "average tone, and global conflict ratio. "
        "Cached in-process for 60 seconds."
    ),
)
def global_pulse(
    start_date: date | None = Query(default=None, description="Inclusive start date (defaults to 7 days ago)"),
    end_date: date | None = Query(default=None, description="Inclusive end date (defaults to today)"),
) -> GlobalPulseResponse:
    now = _time.monotonic()
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=7))
 
    cache_key = f"{start}:{end}"
    with _pulse_cache_lock:
        entry = _pulse_cache.get(cache_key)
        if entry is not None and (now - entry["ts"]) < _PULSE_TTL:
            return entry["data"]
 
    repository = DuckDbRepository(settings)
    metrics = repository.get_global_pulse(start_date=start, end_date=end)
 
    response = GlobalPulseResponse(
        total_events_today=metrics["total_events_today"],
        most_active_country=metrics["most_active_country"],
        most_active_count=metrics["most_active_count"],
        most_hostile_country=metrics["most_hostile_country"],
        avg_global_tone=metrics["avg_global_tone"],
        global_conflict_ratio=metrics["global_conflict_ratio"],
    )
 
    with _pulse_cache_lock:
        _pulse_cache[cache_key] = {"ts": now, "data": response}
        # Evict stale keys
        stale = [k for k, v in _pulse_cache.items() if (now - v["ts"]) > _PULSE_TTL * 5]
        for k in stale:
            _pulse_cache.pop(k, None)
 
    return response
 
 
# ---------------------------------------------------------------------------
# 15.2 — Top Threat Countries endpoint
# ---------------------------------------------------------------------------
 
@router.get(
    "/top-threat-countries",
    response_model=TopThreatCountriesResponse,
    summary="Top countries by threat level",
    description=(
        "Returns the top-N countries ranked by computed risk score "
        "(conflict ratio 40%, Goldstein scale 35%, AvgTone 25%). "
        "Draws from hot-tier DuckDB only. Cached for 120 seconds."
    ),
)
def top_threat_countries(
    limit: int = Query(default=5, ge=1, le=50, description="Number of countries to return"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> TopThreatCountriesResponse:
    now = _time.monotonic()
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=7))
 
    cache_key = f"{start}:{end}:{limit}"
    with _threat_cache_lock:
        entry = _threat_cache.get(cache_key)
        if entry is not None and (now - entry["ts"]) < _THREAT_TTL:
            return entry["data"]
 
    repository = DuckDbRepository(settings)
    rows = repository.get_top_threat_countries(start_date=start, end_date=end, limit=limit)
 
    data = [
        ThreatCountryEntry(
            country_code=r["country_code"],
            score=r["score"],
            conflict_ratio=r["conflict_ratio"],
            total_events=r["total_events"],
        )
        for r in rows
    ]
    response = TopThreatCountriesResponse(count=len(data), data=data)
 
    with _threat_cache_lock:
        _threat_cache[cache_key] = {"ts": now, "data": response}
        stale = [k for k, v in _threat_cache.items() if (now - v["ts"]) > _THREAT_TTL * 5]
        for k in stale:
            _threat_cache.pop(k, None)
 
    return response
 
