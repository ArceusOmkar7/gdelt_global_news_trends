from datetime import date

import pandas as pd

from backend.domain.models.event import EventFilter
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.data_access.duckdb_repository import DuckDbRepository


def _build_settings(tmp_path) -> Settings:
    hot_dir = tmp_path / "hot"
    cache_dir = tmp_path / "cache"
    hot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        gcp_project_id="test-project",
        gdelt_dataset="gdelt-bq.gdeltv2",
        gdelt_table="events_partitioned",
        hot_tier_path=str(hot_dir),
        cache_path=str(cache_dir),
    )


def test_map_aggregations_returns_rows_when_data_matches_window_and_bbox(tmp_path) -> None:
    settings = _build_settings(tmp_path)

    df = pd.DataFrame(
        [
            {
                "GLOBALEVENTID": 1,
                "SQLDATE": 20260318,
                "Actor1CountryCode": "US",
                "Actor2CountryCode": "IR",
                "EventRootCode": "19",
                "EventCode": "190",
                "GoldsteinScale": -5.0,
                "NumMentions": 12,
                "NumSources": 3,
                "AvgTone": -2.1,
                "ActionGeo_CountryCode": "IR",
                "ActionGeo_Lat": 35.7,
                "ActionGeo_Long": 51.4,
                "SOURCEURL": "https://example.com/a",
                "Actor1Type1Code": "GOV",
                "Actor2Type1Code": "MIL",
            }
        ]
    )
    parquet_path = tmp_path / "hot" / "events_202603.parquet"
    df.to_parquet(parquet_path, index=False)

    repo = DuckDbRepository(settings)
    filters = EventFilter(start_date=date(2026, 3, 12), end_date=date(2026, 3, 19), limit=1000)

    result = repo.get_map_aggregations(
        bbox_n=90,
        bbox_s=-90,
        bbox_e=180,
        bbox_w=-180,
        filters=filters,
        grid_precision=1,
    )

    assert len(result) == 1
    assert result[0].intensity == 1
    assert round(result[0].lat, 1) == 35.7
    assert round(result[0].lon, 1) == 51.4
