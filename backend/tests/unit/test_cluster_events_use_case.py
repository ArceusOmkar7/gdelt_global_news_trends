"""Unit tests for ClusterEventsUseCase."""

from datetime import date
from unittest.mock import MagicMock

from backend.application.use_cases.cluster_events import ClusterEventsUseCase
from backend.domain.models.event import Event, EventCluster, EventFilter
from backend.domain.ports.ports import IClusteringService, IEventRepository


def _make_event(id: int) -> Event:
    return Event(global_event_id=id, sql_date=date(2024, 1, 1))

class TestClusterEventsUseCase:
    def setup_method(self):
        self.mock_repo = MagicMock(spec=IEventRepository)
        self.mock_service = MagicMock(spec=IClusteringService)
        self.use_case = ClusterEventsUseCase(
            repository=self.mock_repo,
            clustering_service=self.mock_service
        )

    def test_execute_delegates_to_service(self):
        events = [_make_event(1), _make_event(2)]
        self.mock_repo.get_events.return_value = events
        
        mock_cluster = EventCluster(
            cluster_id=1, label="Test", event_count=2, top_country_codes=[], top_event_codes=[], event_ids=[1, 2]
        )
        self.mock_service.cluster_events.return_value = [mock_cluster]

        filters = EventFilter(limit=100)
        result = self.use_case.execute(filters, n_clusters=3)

        self.mock_repo.get_events.assert_called_once_with(filters)
        self.mock_service.cluster_events.assert_called_once_with(events, 3)
        
        assert len(result) == 1
        assert result[0] == mock_cluster

    def test_execute_clamps_n_clusters(self):
        self.mock_repo.get_events.return_value = [_make_event(1)]
        
        # Requesting 100 clusters should clamp to 20
        self.use_case.execute(EventFilter(), n_clusters=100)
        
        # Verify it passed 20 to the service
        call_args = self.mock_service.cluster_events.call_args
        assert call_args[0][1] == 20
        
        # Requesting 1 should clamp to 2
        self.use_case.execute(EventFilter(), n_clusters=1)
        call_args2 = self.mock_service.cluster_events.call_args
        assert call_args2[0][1] == 2

    def test_execute_empty_data_early_return(self):
        self.mock_repo.get_events.return_value = []
        
        result = self.use_case.execute(EventFilter(), n_clusters=5)
        
        assert result == []
        self.mock_service.cluster_events.assert_not_called()
