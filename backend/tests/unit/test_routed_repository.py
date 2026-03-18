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
        event_root_code="19",
        limit=50,
    )

    first = routed_repo.get_events(filters)
    second = routed_repo.get_events(filters)

    assert [e.global_event_id for e in first] == [42]
    assert [e.global_event_id for e in second] == [42]
    assert cold_repo.get_events.call_count == 1


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
    assert hot_repo.get_events.call_count == 1
    assert cold_repo.get_events.call_count == 1
