"""Use case — retrieve and filter GDELT events.

Orchestrates domain services and repository calls.  Contains no I/O itself;
all data access is delegated to the injected IEventRepository.
"""

from __future__ import annotations

from datetime import date, timedelta

import structlog

from backend.domain.models.event import (
    Event,
    EventCountByDate,
    EventFilter,
    MapAggregation,
    MapEventDetail,
)
from backend.domain.ports.ports import IEventRepository

logger = structlog.get_logger(__name__)


class GetEventsUseCase:
    """Application-layer orchestrator for event retrieval.

    Validates and normalises filter parameters, then delegates to the
    repository port.  This is the single entry point for all event-query
    operations consumed by the API layer.
    """

    def __init__(self, repository: IEventRepository) -> None:
        self._repository = repository

    def execute(self, filters: EventFilter) -> list[Event]:
        """Retrieve events matching the given filters.

        Args:
            filters: Validated filter parameters from the API layer.

        Returns:
            List of domain ``Event`` objects.
        """
        logger.info(
            "get_events_execute",
            start_date=str(filters.start_date),
            end_date=str(filters.end_date),
            country_code=filters.country_code,
            event_root_code=filters.event_root_code,
            limit=filters.limit,
        )
        return self._repository.get_events(filters)

    def get_by_region(
        self,
        country_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 1000,
    ) -> list[Event]:
        """Retrieve events for a specific country/region.

        Args:
            country_code: ISO country code (e.g., ``"US"``, ``"IRQ"``).
            start_date: Optional inclusive start date.
            end_date: Optional inclusive end date.
            limit: Maximum rows to return.

        Returns:
            List of events in the given region.
        """
        filters = EventFilter(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        logger.info(
            "get_events_by_region",
            country_code=country_code,
            start_date=str(start_date),
            end_date=str(end_date),
            limit=limit,
        )
        return self._repository.get_events_by_region(country_code, filters)

    def get_daily_counts(
        self,
        country_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[EventCountByDate]:
        """Get daily-aggregated event counts for charting.

        Args:
            country_code: Optional country filter. ``None`` for global counts.
            start_date: Optional inclusive start date.
            end_date: Optional inclusive end date.

        Returns:
            List of ``EventCountByDate`` records ordered by date ascending.
        """
        filters = EventFilter(
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "get_daily_counts",
            country_code=country_code,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return self._repository.get_event_counts_by_date(country_code, filters)

    def get_map_aggregations(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        start_date: date | None = None,
        end_date: date | None = None,
        event_root_code: str | None = None,
        grid_precision: int = 2,
        limit: int = 10000,
    ) -> list[MapAggregation]:
        """Get aggregated event counts for a geographic region."""
        filters = EventFilter(
            start_date=start_date,
            end_date=end_date,
            event_root_code=event_root_code,
            limit=limit,
        )
        logger.info(
            "get_map_aggregations",
            bbox_n=bbox_n, bbox_s=bbox_s, bbox_e=bbox_e, bbox_w=bbox_w,
            grid_precision=grid_precision,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return self._repository.get_map_aggregations(
            bbox_n, bbox_s, bbox_e, bbox_w, filters, grid_precision
        )

    def get_map_event_details(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        start_date: date | None = None,
        end_date: date | None = None,
        event_root_code: str | None = None,
        limit: int = 5000,
    ) -> list[MapEventDetail]:
        """Get detailed events for a geographic region."""
        filters = EventFilter(
            start_date=start_date,
            end_date=end_date,
            event_root_code=event_root_code,
            limit=limit,
        )
        logger.info(
            "get_map_event_details",
            bbox_n=bbox_n, bbox_s=bbox_s, bbox_e=bbox_e, bbox_w=bbox_w,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return self._repository.get_event_details(
            bbox_n, bbox_s, bbox_e, bbox_w, filters
        )
