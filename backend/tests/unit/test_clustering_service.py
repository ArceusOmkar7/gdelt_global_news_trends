"""Unit tests for the TF-IDF KMeans Clustering Service."""

from datetime import date
from backend.domain.models.event import Event
from backend.domain.services.clustering_service import ClusteringService

def _make_event(id: int, actor1: str, actor2: str, root: str, goldstein: float) -> Event:
    return Event(
        global_event_id=id,
        sql_date=date(2024, 1, 1),
        actor1_country_code=actor1,
        actor2_country_code=actor2,
        event_root_code=root,
        goldstein_scale=goldstein
    )

class TestClusteringService:
    def setup_method(self):
        self.service = ClusteringService()
        
        # A mix of structurally different events to force clusters
        self.events = [
            _make_event(1, "US", "IRQ", "14", -8.0), # War/Conflict
            _make_event(2, "US", "IRQ", "14", -7.5),
            _make_event(3, "US", "IRQ", "14", -9.0),
            
            _make_event(4, "GB", "GB", "03", 4.0),   # Diplomatic/Cooperation
            _make_event(5, "GB", "GB", "03", 5.0),
            
            _make_event(6, "RU", "UKR", "19", -10.0), # Severe Conflict
            _make_event(7, "RU", "UKR", "19", -10.0),
        ]

    def test_empty_events_returns_empty_list(self):
        clusters = self.service.cluster_events([], n_clusters=5)
        assert clusters == []

    def test_clusters_events_into_groups(self):
        # We have 3 clear groups in the dummy data above
        clusters = self.service.cluster_events(self.events, n_clusters=3)
        
        assert len(clusters) == 3
        
        # Sum of event counts should equal total events
        assert sum(c.event_count for c in clusters) == len(self.events)
        
        # Each cluster should have auto-generated labels
        for c in clusters:
            assert len(c.top_country_codes) > 0
            assert len(c.top_event_codes) > 0
            assert c.label is not None

    def test_fewer_events_than_requested_clusters(self):
        # 7 events, try to make 10 clusters -> should cap at 7
        clusters = self.service.cluster_events(self.events, n_clusters=10)
        assert len(clusters) <= len(self.events)

    def test_single_cluster_fallback(self):
        # If we request 1 cluster or pass identical events, it should gracefully handle it
        single = [_make_event(1, "US", "US", "01", 0.0)] * 10
        clusters = self.service.cluster_events(single, n_clusters=3)
        
        assert len(clusters) == 1
        assert clusters[0].event_count == 10
