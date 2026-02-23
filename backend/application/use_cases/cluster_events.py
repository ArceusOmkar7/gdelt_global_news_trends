"""Use case — group GDELT events into thematic clusters."""

from __future__ import annotations

import structlog

from backend.domain.models.event import EventCluster, EventFilter
from backend.domain.ports.ports import IClusteringService, IEventRepository

logger = structlog.get_logger(__name__)


class ClusterEventsUseCase:
    """Application-layer orchestrator for event clustering.
    
    Validates cluster parameters, fetches events from the repository,
    and delegates the NLP clustering to the domain service.
    """

    def __init__(
        self,
        repository: IEventRepository,
        clustering_service: IClusteringService,
    ) -> None:
        self._repository = repository
        self._clustering_service = clustering_service

    def execute(
        self,
        filters: EventFilter,
        n_clusters: int = 5,
    ) -> list[EventCluster]:
        """Fetch events and group them into clusters.
        
        Args:
            filters: Validated filter parameters from the API layer.
            n_clusters: Number of requested clusters (clamped to 2-20).
            
        Returns:
            List of domain `EventCluster` objects.
        """
        # 1. Validate application constraints
        n_clusters = max(2, min(n_clusters, 20))
        
        logger.info(
            "cluster_events_execute",
            n_clusters=n_clusters,
            start_date=str(filters.start_date),
            end_date=str(filters.end_date),
            country_code=filters.country_code,
        )

        # 2. Fetch raw events bounded by filters
        # Clustering needs a decent amount of data but not so much it OOMs locally.
        # Ensure limit is reasonable.
        if filters.limit > 10000:
            filters = filters.model_copy(update={"limit": 10000})

        events = self._repository.get_events(filters)

        if not events:
            logger.info("cluster_events_no_data")
            return []

        # 3. Delegate to domain service
        clusters = self._clustering_service.cluster_events(events, n_clusters)
        
        logger.info(
            "cluster_events_success",
            events_fetched=len(events),
            clusters_returned=len(clusters),
        )
        return clusters
