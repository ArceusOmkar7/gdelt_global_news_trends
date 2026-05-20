import pytest
"""Unit tests for the TF-IDF KMeans Clustering Service."""

from datetime import date
from backend.domain.models.event import Event
from backend.domain.services.clustering_service import ClusteringService

def _make_event(
    id: int, 
    actor1: str | None = None, 
    actor2: str | None = None, 
    root: str | None = None, 
    goldstein: float | None = None,
    themes: list[str] | None = None,
    persons: list[str] | None = None,
    organizations: list[str] | None = None
) -> Event:
    return Event(
        global_event_id=id,
        sql_date=date(2024, 1, 1),
        actor1_country_code=actor1,
        actor2_country_code=actor2,
        event_root_code=root,
        goldstein_scale=goldstein,
        themes=themes or [],
        persons=persons or [],
        organizations=organizations or []
    )

class TestClusteringService:
    def setup_method(self):
        self.service = ClusteringService()
        
        # A mix of structurally different events to force clusters
        self.events = [
            _make_event(1, "US", "IRQ", "14", -8.0, themes=["TERROR"], persons=["Bush"]),
            _make_event(2, "US", "IRQ", "14", -7.5, themes=["TERROR"], persons=["Bush"]),
            _make_event(3, "US", "IRQ", "14", -9.0, themes=["MILITARY"]),
            
            _make_event(4, "GB", "GB", "03", 4.0, themes=["ECON_TRADE"]),
            _make_event(5, "GB", "GB", "03", 5.0, themes=["ECON_TRADE"], organizations=["EU"]),
            
            _make_event(6, "RU", "UKR", "19", -10.0, themes=["WAR"], persons=["Putin"]),
            _make_event(7, "RU", "UKR", "19", -10.0, themes=["WAR", "SANCTIONS"], persons=["Putin", "Zelenskyy"]),
        ]

    def test_empty_events_returns_empty_list(self):
        clusters = self.service.cluster_events([], n_clusters=5)
        assert clusters == []

    def test_clusters_events_into_groups(self):
        clusters = self.service.cluster_events(self.events, n_clusters=3)
        assert len(clusters) == 3
        assert sum(c.event_count for c in clusters) == len(self.events)
        for c in clusters:
            assert len(c.top_country_codes) >= 0
            assert c.label is not None
            assert c.avg_goldstein_scale is not None

    def test_fewer_events_than_requested_clusters(self):
        clusters = self.service.cluster_events(self.events, n_clusters=10)
        assert len(clusters) <= len(self.events)

    def test_single_cluster_fallback(self):
        single = [_make_event(1, "US", "US", "01", 0.0)] * 10
        clusters = self.service.cluster_events(single, n_clusters=3)
        assert len(clusters) == 1
        assert clusters[0].event_count == 10

    def test_event_to_text(self):
        e1 = _make_event(1, "US", "UK", "19", 2.0)
        text1 = self.service._event_to_text(e1)
        assert "actor_us" in text1
        assert "actor_uk" in text1
        assert "event_19" in text1
        assert "tone_positive" in text1
        
        e2 = _make_event(2)
        text2 = self.service._event_to_text(e2)
        assert text2 == "unknown_features"

    def test_build_cluster_model(self):
        cluster_events = [
            _make_event(1, "US", "UK", "19", 2.0, themes=["A", "B"]),
            _make_event(2, "US", "FR", "19", 4.0, themes=["A", "C"]),
            _make_event(3, "DE", None, "14", -2.0, themes=["B", "C"])
        ]
        
        cluster = self.service._build_cluster_model(cluster_id=1, events=cluster_events)
        
        assert cluster.cluster_id == 1
        assert cluster.event_count == 3
        # avg = (2.0 + 4.0 - 2.0) / 3 = 4.0 / 3 = 1.333
        assert pytest.approx(cluster.avg_goldstein_scale, 0.01) == 1.33
        assert "US" in cluster.top_country_codes
        assert len(cluster.event_ids) == 3
        assert cluster.label != "Unknown Cluster"

