"""Unit tests for domain models — validates Pydantic schemas and constraints."""

from datetime import date
import pytest

from backend.domain.models.event import (
    Event, 
    EventCountByDate, 
    EventFilter,
    EventCluster,
    ForecastPoint,
    ForecastResult,
    MapAggregation,
    MapEventDetail,
    ExtractedArticle,
    EventAnalysis,
    EntityGroup
)

class TestEvent:
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
    def test_default_values(self) -> None:
        f = EventFilter()
        assert f.start_date is None
        assert f.end_date is None
        assert f.country_code is None
        assert f.event_root_codes is None
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
            event_root_codes=["14"],
            limit=500,
        )
        assert f.country_code == "US"
        assert f.limit == 500

class TestEventCountByDate:
    def test_create_valid_count(self) -> None:
        count = EventCountByDate(
            date=date(2024, 1, 15),
            count=1500,
            avg_goldstein_scale=-2.1,
            total_mentions=50000,
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

class TestEventCluster:
    def test_create_event_cluster(self):
        event1 = Event(global_event_id=1, sql_date=date(2024, 1, 1))
        cluster = EventCluster(
            cluster_id=1,
            label="Elections",
            event_count=1,
            avg_goldstein_scale=2.0,
            top_country_codes=["US"],
            top_event_codes=[],
            event_ids=[1]
        )
        assert cluster.cluster_id == 1
        assert cluster.event_count == 1
        
    def test_frozen(self):
        cluster = EventCluster(cluster_id=1, label="L", event_count=1, top_country_codes=[], top_event_codes=[], event_ids=[])
        with pytest.raises(Exception):
            cluster.event_count = 2

class TestForecastModels:
    def test_forecast_point(self):
        point = ForecastPoint(date=date(2024, 1, 1), predicted_count=100.5, lower_bound=50.0, upper_bound=150.0)
        assert point.date == date(2024, 1, 1)
        assert point.predicted_count == 100.5
        
        # Test frozen
        with pytest.raises(Exception):
            point.predicted_count = 200.0
            
    def test_forecast_result(self):
        point = ForecastPoint(date=date(2024, 1, 1), predicted_count=100.5, lower_bound=50.0, upper_bound=150.0)
        result = ForecastResult(
            horizon_days=1,
            country_code="US",
            model_type="prophet",
            predictions=[point]
        )
        assert result.horizon_days == 1
        assert result.country_code == "US"
        assert result.model_type == "prophet"
        assert len(result.predictions) == 1

class TestMapModels:
    def test_map_aggregation(self):
        agg = MapAggregation(lat=10.0, lon=20.0, intensity=5.5)
        assert agg.lat == 10.0
        assert agg.lon == 20.0
        assert agg.intensity == 5.5
        assert agg.country_code is None
        
    def test_map_event_detail(self):
        detail = MapEventDetail(
            global_event_id=1,
            sql_date=date(2024, 1, 1),
            lat=10.0,
            lon=20.0
        )
        assert detail.global_event_id == 1
        assert detail.lat == 10.0
        assert detail.num_mentions == 0
        
class TestAnalysisModels:
    def test_extracted_article(self):
        article = ExtractedArticle(
            title="Title",
            text="Content",
            images=["img1.jpg"],
            embeds=[]
        )
        assert article.title == "Title"
        assert article.text == "Content"
        assert len(article.images) == 1
        
    def test_event_analysis(self):
        analysis = EventAnalysis(
            summary="Summary",
            sentiment="Positive",
            entities=EntityGroup(persons=["Joe"]),
            themes=["Politics"],
            confidence=0.9,
            images=[],
            embeds=[]
        )
        assert analysis.sentiment == "Positive"
        assert analysis.confidence == 0.9
