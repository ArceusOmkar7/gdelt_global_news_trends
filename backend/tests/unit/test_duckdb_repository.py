from datetime import date
import pytest

from backend.domain.models.event import EventFilter
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository, DuckDbRepositoryError

class TestDuckDbRepository:
    def test_init_with_no_parquet_files(self, tmp_path, test_settings):
        # Point to an empty directory
        test_settings.hot_tier_path = str(tmp_path)
        with pytest.raises(DuckDbRepositoryError, match="No parquet files"):
            DuckDbRepository(test_settings)
            
    def test_init_with_invalid_path(self, test_settings):
        test_settings.hot_tier_path = "/does/not/exist/12345"
        with pytest.raises(DuckDbRepositoryError, match="does not exist or is not a directory"):
            DuckDbRepository(test_settings)

    def test_get_events_basic(self, test_settings, tmp_hot_tier):
        # tmp_hot_tier fixture gives us valid Parquet files (see conftest.py)
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(limit=10)
        
        events = repo.get_events(filters)
        assert len(events) > 0
        
    def test_get_events_date_filter(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            limit=10
        )
        
        events = repo.get_events(filters)
        assert len(events) == 3 # ID 101, 102, 103 are within these dates in conftest
        
        # Verify dates
        for e in events:
            assert date(2024, 1, 1) <= e.sql_date <= date(2024, 1, 2)

    def test_get_events_country_filter(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(country_code="US")
        
        events = repo.get_events(filters)
        assert len(events) > 0
        for e in events:
            assert e.actor1_country_code == "US" or e.action_geo_country_code == "US"

    def test_get_event_counts_by_date(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(start_date=date(2024, 1, 1), end_date=date(2024, 1, 5))
        
        counts = repo.get_event_counts_by_date(country_code=None, filters=filters)
        assert len(counts) > 0
        assert counts[0].count > 0

    def test_get_top_people_aggregates_person_mentions(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(start_date=date(2024, 1, 1), end_date=date(2024, 1, 3), limit=10)

        people = repo.get_top_people(filters, limit=5)

        assert len(people) == 5
        counts = {p['name']: p['count'] for p in people}
        assert counts['Vladimir Putin'] == 500
        assert counts['Volodymyr Zelenskyy'] == 500
        assert counts['Joe Biden'] == 100
        assert 'Rishi Sunak' in counts

    def test_get_top_sources_aggregates_source_domains(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(start_date=date(2024, 1, 1), end_date=date(2024, 1, 4), limit=10)

        sources = repo.get_top_sources(filters, limit=5)

        assert len(sources) == 3
        counts = {s['name']: s['count'] for s in sources}
        assert counts['example.com'] == 3
        assert counts['bbc.com'] == 1
        assert counts['example.org'] == 1

    def test_get_event_by_id(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        
        # ID 101 exists in our mock data
        event = repo.get_event_by_id(101)
        assert event is not None
        assert event.global_event_id == 101
        
        # ID 999 does not exist
        missing = repo.get_event_by_id(999)
        assert missing is None

    def test_get_map_aggregations(self, test_settings, tmp_hot_tier):
        repo = DuckDbRepository(test_settings)
        filters = EventFilter(limit=1000)

        result = repo.get_map_aggregations(
            bbox_n=90,
            bbox_s=-90,
            bbox_e=180,
            bbox_w=-180,
            filters=filters,
            grid_precision=1,
        )

        assert len(result) > 0
        assert result[0].intensity >= 1
