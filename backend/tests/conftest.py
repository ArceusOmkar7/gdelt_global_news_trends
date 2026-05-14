import os
import shutil
import tempfile
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
import backend.api.main as main_module
from backend.domain.models.event import Event, EventCountByDate
from backend.domain.ports.ports import IEventRepository
from backend.infrastructure.config.settings import Settings

@pytest.fixture(scope="session")
def tmp_hot_tier():
    """Create a temporary directory with a real Parquet file for testing DuckDB."""
    tmp_dir = tempfile.mkdtemp(prefix="gniem-hot-tier-")
    
    # Create diverse sample data
    data = [
        {
            "GLOBALEVENTID": 101,
            "SQLDATE": 20240101,
            "Actor1CountryCode": "US",
            "Actor2CountryCode": "CN",
            "EventRootCode": "01",
            "EventCode": "010",
            "GoldsteinScale": 0.0,
            "NumMentions": 100,
            "NumSources": 10,
            "AvgTone": 1.5,
            "ActionGeo_CountryCode": "US",
            "ActionGeo_Lat": 38.9,
            "ActionGeo_Long": -77.0,
            "SOURCEURL": "https://example.com/101",
            "Actor1Type1Code": "GOV",
            "Actor2Type1Code": "GOV",
            "QuadClass": 1,
            "themes": ["POLITICS", "LEGISLATION"],
            "persons": ["Joe Biden", "Xi Jinping"],
            "organizations": ["UN", "WHO"],
            "mentions_count": 10,
            "avg_confidence": 95,
        },
        {
            "GLOBALEVENTID": 102,
            "SQLDATE": 20240101,
            "Actor1CountryCode": "RU",
            "Actor2CountryCode": "UA",
            "EventRootCode": "19",
            "EventCode": "190",
            "GoldsteinScale": -10.0,
            "NumMentions": 500,
            "NumSources": 50,
            "AvgTone": -8.5,
            "ActionGeo_CountryCode": "UA",
            "ActionGeo_Lat": 50.45,
            "ActionGeo_Long": 30.52,
            "SOURCEURL": "https://example.com/102",
            "Actor1Type1Code": "MIL",
            "Actor2Type1Code": "MIL",
            "QuadClass": 4,
            "themes": ["TERROR", "TAX_MILITARY"],
            "persons": ["Vladimir Putin", "Volodymyr Zelenskyy"],
            "organizations": ["NATO"],
            "mentions_count": 50,
            "avg_confidence": 80,
        },
        {
            "GLOBALEVENTID": 103,
            "SQLDATE": 20240102,
            "Actor1CountryCode": "GB",
            "Actor2CountryCode": "FR",
            "EventRootCode": "07",
            "EventCode": "070",
            "GoldsteinScale": 7.0,
            "NumMentions": 50,
            "NumSources": 5,
            "AvgTone": 5.0,
            "ActionGeo_CountryCode": "GB",
            "ActionGeo_Lat": 51.5,
            "ActionGeo_Long": -0.12,
            "SOURCEURL": "https://example.com/103",
            "Actor1Type1Code": "BUS",
            "Actor2Type1Code": "GOV",
            "QuadClass": 2,
            "themes": ["ECON_TRADE", "MARKET"],
            "persons": ["Rishi Sunak"],
            "organizations": ["EU"],
            "mentions_count": 5,
            "avg_confidence": 99,
        },
        {
            "GLOBALEVENTID": 104,
            "SQLDATE": 20240103,
            "Actor1CountryCode": "IL",
            "Actor2CountryCode": "PS",
            "EventRootCode": "19",
            "EventCode": "192",
            "GoldsteinScale": -9.0,
            "NumMentions": 1000,
            "NumSources": 100,
            "AvgTone": -9.5,
            "ActionGeo_CountryCode": "IL",
            "ActionGeo_Lat": 31.7,
            "ActionGeo_Long": 35.2,
            "SOURCEURL": "https://example.com/104",
            "Actor1Type1Code": "MIL",
            "Actor2Type1Code": "REB",
            "QuadClass": 4,
            "themes": ["TERROR", "HUMAN_RIGHTS"],
            "persons": [],
            "organizations": ["UN"],
            "mentions_count": 100,
            "avg_confidence": 85,
        },
        {
            "GLOBALEVENTID": 105,
            "SQLDATE": 20240104,
            "Actor1CountryCode": "BR",
            "Actor2CountryCode": None,
            "EventRootCode": "03",
            "EventCode": "030",
            "GoldsteinScale": 4.0,
            "NumMentions": 20,
            "NumSources": 2,
            "AvgTone": 2.0,
            "ActionGeo_CountryCode": "BR",
            "ActionGeo_Lat": -15.7,
            "ActionGeo_Long": -47.8,
            "SOURCEURL": "https://example.com/105",
            "Actor1Type1Code": "ENV",
            "Actor2Type1Code": None,
            "QuadClass": 1,
            "themes": ["ENV_CLIMATE"],
            "persons": [],
            "organizations": ["NGO"],
            "mentions_count": 2,
            "avg_confidence": 70,
        }
    ]
    
    df = pd.DataFrame(data)
    # Ensure SQLDATE is INT
    df["SQLDATE"] = df["SQLDATE"].astype(int)
    
    parquet_path = os.path.join(tmp_dir, "test_events.parquet")
    df.to_parquet(parquet_path, index=False)
    
    yield tmp_dir
    
    # Cleanup
    shutil.rmtree(tmp_dir)

@pytest.fixture
def test_settings(tmp_hot_tier):
    cache_dir = os.path.join(tmp_hot_tier, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return Settings(
        gcp_project_id="test-project",
        gdelt_dataset="test_dataset",
        gdelt_table="test_table",
        hot_tier_path=tmp_hot_tier,
        cache_path=cache_dir,
        groq_api_key="test-key",
        jina_api_key="test-key"
    )

@pytest.fixture
def mock_repo():
    return MagicMock(spec=IEventRepository)

@pytest.fixture
def test_client(test_settings):
    main_module.settings = test_settings
    with TestClient(app) as client:
        yield client

@pytest.fixture
def sample_events():
    return [
        Event(
            global_event_id=1,
            sql_date=date(2024, 1, 1),
            actor1_country_code="US",
            event_root_code="01",
            goldstein_scale=1.0,
            num_mentions=100,
            avg_tone=2.0
        ),
        Event(
            global_event_id=2,
            sql_date=date(2024, 1, 2),
            actor1_country_code="RU",
            event_root_code="19",
            goldstein_scale=-10.0,
            num_mentions=500,
            avg_tone=-8.0
        )
    ]

@pytest.fixture
def sample_counts():
    return [
        EventCountByDate(date=date(2024, 1, 1), count=100, avg_goldstein_scale=-1.0, total_mentions=1000, avg_tone=-2.0),
        EventCountByDate(date=date(2024, 1, 2), count=150, avg_goldstein_scale=-2.0, total_mentions=1500, avg_tone=-3.0),
        EventCountByDate(date=date(2024, 1, 3), count=120, avg_goldstein_scale=0.5, total_mentions=1200, avg_tone=1.0),
    ]
