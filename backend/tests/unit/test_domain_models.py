"""Unit tests for domain models — validates Pydantic schemas and constraints."""

from datetime import date

import pytest

from backend.domain.models.event import Event, EventCountByDate, EventFilter


class TestEvent:
    """Tests for the Event domain model."""

    def test_create_valid_event(self) -> None:
        event = Event(
            global_event_id=123456789,
            sql_date=date(2024, 1, 15),
            actor1_country_code="US",
            actor2_country_code="IRQ",
            event_root_code="14",
            event_code="142",
            goldstein_scale=-6.5,
            num_mentions=25,
            num_articles=10,
            num_sources=5,
            avg_tone=-3.2,
            action_geo_country_code="IRQ",
            action_geo_lat=33.3,
            action_geo_long=44.4,
            source_url="https://example.com/article",
        )
        assert event.global_event_id == 123456789
        assert event.sql_date == date(2024, 1, 15)
        assert event.goldstein_scale == -6.5
        assert event.actor1_country_code == "US"

    def test_event_with_optional_fields_none(self) -> None:
        event = Event(
            global_event_id=1,
            sql_date=date(2024, 1, 1),
        )
        assert event.actor1_country_code is None
        assert event.goldstein_scale is None
        assert event.action_geo_lat is None
        assert event.num_mentions == 0

    def test_event_is_frozen(self) -> None:
        event = Event(global_event_id=1, sql_date=date(2024, 1, 1))
        with pytest.raises(Exception):
            event.global_event_id = 999  # type: ignore[misc]

    def test_event_serialisation_roundtrip(self) -> None:
        original = Event(
            global_event_id=42,
            sql_date=date(2024, 6, 1),
            actor1_country_code="RUS",
            goldstein_scale=3.0,
            num_mentions=100,
        )
        data = original.model_dump()
        restored = Event.model_validate(data)
        assert restored == original


class TestEventFilter:
    """Tests for the EventFilter model."""

    def test_default_values(self) -> None:
        f = EventFilter()
        assert f.start_date is None
        assert f.end_date is None
        assert f.country_code is None
        assert f.event_root_code is None
        assert f.limit == 1000

    def test_limit_min_constraint(self) -> None:
        with pytest.raises(Exception):
            EventFilter(limit=0)

    def test_limit_max_constraint(self) -> None:
        with pytest.raises(Exception):
            EventFilter(limit=200_000)

    def test_valid_filter(self) -> None:
        f = EventFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            country_code="US",
            event_root_code="14",
            limit=500,
        )
        assert f.country_code == "US"
        assert f.limit == 500


class TestEventCountByDate:
    """Tests for the EventCountByDate model."""

    def test_create_valid_count(self) -> None:
        count = EventCountByDate(
            date=date(2024, 1, 15),
            count=1500,
            avg_goldstein_scale=-2.1,
            total_mentions=50000,
            total_articles=20000,
            avg_tone=-1.5,
        )
        assert count.count == 1500
        assert count.avg_goldstein_scale == -2.1

    def test_count_with_defaults(self) -> None:
        count = EventCountByDate(
            date=date(2024, 1, 15),
            count=100,
        )
        assert count.avg_goldstein_scale is None
        assert count.total_mentions == 0

    def test_count_is_frozen(self) -> None:
        count = EventCountByDate(date=date(2024, 1, 1), count=10)
        with pytest.raises(Exception):
            count.count = 999  # type: ignore[misc]
