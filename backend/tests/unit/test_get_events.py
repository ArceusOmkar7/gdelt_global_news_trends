"""Unit tests for GetEventsUseCase — all I/O is mocked."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.get_events import GetEventsUseCase
from backend.domain.models.event import Event, EventCountByDate, EventFilter
from backend.domain.ports.ports import IEventRepository


def _make_event(**overrides) -> Event:
    """Factory helper for creating test Event instances."""
    defaults = {
        "global_event_id": 1,
        "sql_date": date(2024, 1, 15),
        "actor1_country_code": "US",
        "goldstein_scale": -3.0,
        "num_mentions": 10,
        "num_articles": 5,
    }
    defaults.update(overrides)
    return Event(**defaults)


def _make_count(**overrides) -> EventCountByDate:
    """Factory helper for creating test EventCountByDate instances."""
    defaults = {
        "date": date(2024, 1, 15),
        "count": 100,
        "avg_goldstein_scale": -2.0,
        "total_mentions": 5000,
    }
    defaults.update(overrides)
    return EventCountByDate(**defaults)


class TestGetEventsUseCase:
    """Tests for the GetEventsUseCase orchestrator."""

    def setup_method(self) -> None:
        self.mock_repo = MagicMock(spec=IEventRepository)
        self.use_case = GetEventsUseCase(repository=self.mock_repo)

    def test_execute_delegates_to_repository(self) -> None:
        expected = [_make_event(global_event_id=1), _make_event(global_event_id=2)]
        self.mock_repo.get_events.return_value = expected

        filters = EventFilter(limit=10)
        result = self.use_case.execute(filters)

        self.mock_repo.get_events.assert_called_once_with(filters)
        assert result == expected

    def test_execute_with_date_range(self) -> None:
        self.mock_repo.get_events.return_value = []

        filters = EventFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )
        result = self.use_case.execute(filters)

        self.mock_repo.get_events.assert_called_once_with(filters)
        assert result == []

    def test_get_by_region_delegates_to_repository(self) -> None:
        expected = [_make_event(actor1_country_code="IRQ")]
        self.mock_repo.get_events_by_region.return_value = expected

        result = self.use_case.get_by_region(
            country_code="IRQ",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            limit=50,
        )

        self.mock_repo.get_events_by_region.assert_called_once()
        call_args = self.mock_repo.get_events_by_region.call_args
        assert call_args[0][0] == "IRQ"
        assert result == expected

    def test_get_daily_counts_with_country(self) -> None:
        expected = [
            _make_count(date=date(2024, 1, 1), count=50),
            _make_count(date=date(2024, 1, 2), count=75),
        ]
        self.mock_repo.get_event_counts_by_date.return_value = expected

        result = self.use_case.get_daily_counts(
            country_code="US",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 7),
        )

        self.mock_repo.get_event_counts_by_date.assert_called_once()
        call_args = self.mock_repo.get_event_counts_by_date.call_args
        assert call_args[0][0] == "US"
        assert result == expected

    def test_get_daily_counts_global(self) -> None:
        self.mock_repo.get_event_counts_by_date.return_value = []

        result = self.use_case.get_daily_counts(country_code=None)

        call_args = self.mock_repo.get_event_counts_by_date.call_args
        assert call_args[0][0] is None
        assert result == []
