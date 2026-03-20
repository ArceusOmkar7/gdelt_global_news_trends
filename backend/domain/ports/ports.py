"""Domain ports — abstract interfaces that define the boundaries of the domain.

Infrastructure implementations (BigQuery, caching, etc.) implement these ports.
Domain and application layers depend ONLY on these interfaces, never on concrete
infrastructure classes.  This is the core inversion-of-control mechanism.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.models.event import (
    Event,
    EventCluster,
    EventCountByDate,
    EventFilter,
    ForecastResult,
    MapAggregation,
    MapEventDetail,
    EventAnalysis,
)


class IEventRepository(ABC):
    """Interface for accessing GDELT event data.

    Concrete implementations live in ``infrastructure/data_access/``.
    """

    @abstractmethod
    def get_events(self, filters: EventFilter) -> list[Event]:
        """Retrieve events matching the given filters.

        Args:
            filters: Typed filter parameters (dates, country, event code, limit).

        Returns:
            List of domain Event objects, ordered by date descending.
        """

    @abstractmethod
    def get_events_by_region(
        self,
        country_code: str,
        filters: EventFilter,
    ) -> list[Event]:
        """Retrieve events for a specific country/region.

        Args:
            country_code: ISO 3166 alpha-2 or alpha-3 country code.
            filters: Additional filter parameters.

        Returns:
            List of events where the action took place in the given country.
        """

    @abstractmethod
    def get_event_counts_by_date(
        self,
        country_code: str | None,
        filters: EventFilter,
    ) -> list[EventCountByDate]:
        """Get daily-aggregated event counts, optionally filtered by country.

        Args:
            country_code: Optional country filter. If ``None``, returns global counts.
            filters: Date range and other filter parameters.

        Returns:
            List of ``EventCountByDate`` records ordered by date ascending.
        """

    @abstractmethod
    def get_map_aggregations(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
        grid_precision: int = 2
    ) -> list[MapAggregation]:
        """Get aggregated event counts for a geographic region.

        Args:
            bbox_n: North latitude bound.
            bbox_s: South latitude bound.
            bbox_e: East longitude bound.
            bbox_w: West longitude bound.
            filters: Additional filter parameters.
            grid_precision: Number of decimal places to round lat/lon for grouping.
        """

    @abstractmethod
    def get_event_details(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
        min_mentions: int = 1,
    ) -> list[MapEventDetail]:
        """Get detailed events for a geographic region."""

    @abstractmethod
    def get_event_by_id(self, event_id: int) -> Event | None:
        """Retrieve a single event by its unique GLOBALEVENTID."""


class IClusteringService(ABC):
    """Interface for NLP-based event clustering."""

    @abstractmethod
    def cluster_events(self, events: list[Event], n_clusters: int) -> list[EventCluster]:
        """Group events into thematic clusters.
        
        Args:
            events: List of domain Event objects to cluster.
            n_clusters: The desired number of clusters to form.
            
        Returns:
            A list of EventCluster models.
        """


class IForecastingService(ABC):
    """Interface for time-series conflict forecasting."""

    @abstractmethod
    def forecast(
        self,
        historical_counts: list[EventCountByDate],
        horizon_days: int,
        country_code: str | None = None,
    ) -> ForecastResult:
        """Produce a forecast from historical event counts.
        
        Args:
            historical_counts: Daily event counts used as training data.
            horizon_days: How many days into the future to predict.
            country_code: Optional country code context for the result metadata.
            
        Returns:
            A ForecastResult containing the predictions.
        """


class ILLMAnalysisService(ABC):
    """Interface for on-demand LLM intelligence analysis."""

    @abstractmethod
    async def analyze_event(self, article_text: str) -> EventAnalysis:
        """Perform deep analysis on article text using an LLM.

        Args:
            article_text: The full text content of a news article.

        Returns:
            An EventAnalysis object containing summary, entities, etc.
        """
