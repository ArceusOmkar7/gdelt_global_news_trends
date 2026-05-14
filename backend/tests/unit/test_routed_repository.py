"""Unit tests for RoutedRepository hot/cold selection and policy rules."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from backend.api.request_context import set_request_user_id
from backend.domain.models.event import Event, EventFilter
from backend.domain.ports.ports import IEventRepository
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.data_access.routed_repository import (
    ColdTierPolicyError,
    RoutedRepository,
)


def _make_event(event_id: int, sql_date: date) -> Event:
    return Event(
        global_event_id=event_id,
        sql_date=sql_date,
        actor1_country_code="US",
        num_mentions=1,
        num_sources=1,
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        gcp_project_id="test-project",
        cache_path=str(tmp_path / "cache"),
        hot_tier_cutoff_days=90,
        cold_tier_max_window_days=30,
        cold_tier_monthly_query_limit=3,
        default_lookback_days=7,
        default_query_limit=1000,
    )


@pytest.fixture
def hot_repo() -> MagicMock:
    return MagicMock(spec=IEventRepository)


@pytest.fixture
def cold_repo() -> MagicMock:
    return MagicMock(spec=IEventRepository)


@pytest.fixture
def routed_repo(hot_repo: MagicMock, cold_repo: MagicMock, settings: Settings) -> RoutedRepository:
    return RoutedRepository(hot_repo, cold_repo, settings)


def test_uses_hot_repo_for_recent_window(routed_repo: RoutedRepository, hot_repo: MagicMock, cold_repo: MagicMock) -> None:
    today = date.today()
    event = _make_event(1, today)
    hot_repo.get_events.return_value = [event]

    filters = EventFilter(start_date=today - timedelta(days=7), end_date=today, limit=100)
    result = routed_repo.get_events(filters)

    assert result == [event]
    hot_repo.get_events.assert_called_once()
    cold_repo.get_events.assert_not_called()


def test_enforces_cold_window_limit(routed_repo: RoutedRepository) -> None:
    set_request_user_id("user-window")
    today = date.today()
    end = today - timedelta(days=100)
    start = end - timedelta(days=45)

    filters = EventFilter(start_date=start, end_date=end, limit=100)

    with pytest.raises(ColdTierPolicyError, match="date window exceeds"):
        routed_repo.get_events(filters)


def test_enforces_monthly_cold_query_limit(
    routed_repo: RoutedRepository,
    cold_repo: MagicMock,
) -> None:
    set_request_user_id("user-quota")
    cold_repo.get_events.return_value = []

    today = date.today()
    base_end = today - timedelta(days=120)

    for idx in range(3):
        end = base_end - timedelta(days=idx)
        start = end - timedelta(days=10)
        routed_repo.get_events(EventFilter(start_date=start, end_date=end, limit=100))

    with pytest.raises(ColdTierPolicyError, match="monthly user limit"):
        end = base_end - timedelta(days=4)
        start = end - timedelta(days=10)
        routed_repo.get_events(EventFilter(start_date=start, end_date=end, limit=100))


def test_uses_cache_for_identical_cold_request(
    routed_repo: RoutedRepository,
    cold_repo: MagicMock,
) -> None:
    set_request_user_id("user-cache")
    old_date = date.today() - timedelta(days=120)
    cached_event = _make_event(42, old_date)
    cold_repo.get_events.return_value = [cached_event]

    filters = EventFilter(
        start_date=old_date - timedelta(days=5),
        end_date=old_date,
        country_code="US",
        event_root_codes=["19"],
        limit=50,
    )

    first = routed_repo.get_events(filters)
    second = routed_repo.get_events(filters)

    assert [e.global_event_id for e in first] == [42]
    assert [e.global_event_id for e in second] == [42]
    assert cold_repo.get_events.call_count == 1


    def test_hybrid_window_merges_hot_and_cold(
        self,
        routed_repo: RoutedRepository,
        hot_repo: MagicMock,
        cold_repo: MagicMock,
    ) -> None:
        pass # Not a class method originally

def test_hybrid_window_merges_hot_and_cold(
    routed_repo: RoutedRepository,
    hot_repo: MagicMock,
    cold_repo: MagicMock,
) -> None:
    set_request_user_id("user-hybrid")
    cutoff = date.today() - timedelta(days=90)

    cold_repo.get_events.return_value = [_make_event(1, cutoff - timedelta(days=2))]
    hot_repo.get_events.return_value = [_make_event(2, cutoff + timedelta(days=1))]

    filters = EventFilter(
        start_date=cutoff - timedelta(days=5),
        end_date=cutoff + timedelta(days=2),
        limit=100,
    )

    results = routed_repo.get_events(filters)

    assert [row.global_event_id for row in results] == [2, 1]

def test_get_event_by_id_hot_and_cold(routed_repo: RoutedRepository, hot_repo: MagicMock, cold_repo: MagicMock):
    # Found in hot
    hot_repo.get_event_by_id.return_value = _make_event(1, date.today())
    res1 = routed_repo.get_event_by_id(1)
    assert res1 is not None
    assert res1.global_event_id == 1
    cold_repo.get_event_by_id.assert_not_called()

    # Not found in hot, fallback to cold
    hot_repo.get_event_by_id.return_value = None
    cold_repo.get_event_by_id.return_value = _make_event(2, date.today())
    res2 = routed_repo.get_event_by_id(2)
    assert res2 is not None
    assert res2.global_event_id == 2
    cold_repo.get_event_by_id.assert_called_once_with(2)

def test_get_map_aggregations_routing(routed_repo: RoutedRepository, hot_repo: MagicMock, cold_repo: MagicMock):
    cutoff = date.today() - timedelta(days=90)
    hot_repo._resolve_dates.return_value = (cutoff - timedelta(days=5), cutoff + timedelta(days=5))
    
    # Test hot only
    hot_filters = EventFilter(start_date=cutoff + timedelta(days=1), end_date=cutoff + timedelta(days=5))
    hot_repo._resolve_dates.return_value = (cutoff + timedelta(days=1), cutoff + timedelta(days=5))
    routed_repo.get_map_aggregations(10, 0, 10, 0, hot_filters, 1)
    hot_repo.get_map_aggregations.assert_called_once()
    cold_repo.get_map_aggregations.assert_not_called()
    
    # Reset mocks
    hot_repo.reset_mock()
    cold_repo.reset_mock()

    # Test hybrid
    hybrid_filters = EventFilter(start_date=cutoff - timedelta(days=5), end_date=cutoff + timedelta(days=5))
    hot_repo._resolve_dates.return_value = (cutoff - timedelta(days=5), cutoff + timedelta(days=5))
    
    from backend.domain.models.event import MapAggregation
    hot_repo.get_map_aggregations.return_value = [MapAggregation(lat=10.0, lon=10.0, intensity=5.0)]
    cold_repo.get_map_aggregations.return_value = [MapAggregation(lat=10.0, lon=10.0, intensity=2.0)]
    
    res = routed_repo.get_map_aggregations(10, 0, 10, 0, hybrid_filters, 1)
    assert len(res) == 1
    assert res[0].intensity == 7.0 # Merged intensity
    
def test_get_event_counts_by_date_routing(routed_repo: RoutedRepository, hot_repo: MagicMock, cold_repo: MagicMock):
    cutoff = date.today() - timedelta(days=90)
    
    # Hybrid
    hybrid_filters = EventFilter(start_date=cutoff - timedelta(days=2), end_date=cutoff + timedelta(days=2))
    hot_repo._resolve_dates.return_value = (cutoff - timedelta(days=2), cutoff + timedelta(days=2))
    
    from backend.domain.models.event import EventCountByDate
    hot_repo.get_event_counts_by_date.return_value = [
        EventCountByDate(date=cutoff + timedelta(days=1), count=100, avg_goldstein_scale=2.0, total_mentions=50, avg_tone=1.0)
    ]
    cold_repo.get_event_counts_by_date.return_value = [
        EventCountByDate(date=cutoff - timedelta(days=1), count=50, avg_goldstein_scale=-2.0, total_mentions=10, avg_tone=-1.0),
        EventCountByDate(date=cutoff + timedelta(days=1), count=10, avg_goldstein_scale=1.0, total_mentions=5, avg_tone=0.5) # overlapping date
    ]
    
    res = routed_repo.get_event_counts_by_date(None, hybrid_filters)
    assert len(res) == 2
    
    # The overlapping date (cutoff + 1) should be merged
    overlap = next(r for r in res if r.date == cutoff + timedelta(days=1))
    assert overlap.count == 110
    assert overlap.total_mentions == 55
    
def test_get_event_details_routing(routed_repo: RoutedRepository, hot_repo: MagicMock, cold_repo: MagicMock):
    cutoff = date.today() - timedelta(days=90)
    
    # Hybrid
    hybrid_filters = EventFilter(start_date=cutoff - timedelta(days=5), end_date=cutoff + timedelta(days=5))
    hot_repo._resolve_dates.return_value = (cutoff - timedelta(days=5), cutoff + timedelta(days=5))
    
    from backend.domain.models.event import MapEventDetail
    hot_repo.get_event_details.return_value = [
        MapEventDetail(global_event_id=1, sql_date=cutoff + timedelta(days=1), lat=0.0, lon=0.0)
    ]
    cold_repo.get_event_details.return_value = [
        MapEventDetail(global_event_id=2, sql_date=cutoff - timedelta(days=1), lat=0.0, lon=0.0)
    ]
    
    res = routed_repo.get_event_details(10, 0, 10, 0, hybrid_filters, 100)
    assert len(res) == 2
    assert {e.global_event_id for e in res} == {1, 2}
