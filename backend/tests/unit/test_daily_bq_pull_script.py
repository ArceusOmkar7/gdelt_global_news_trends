from datetime import date

import pandas as pd

from scripts.daily_bq_pull import (
    clean_v2_split,
    fetch_events,
    parse_args,
    sql_date_bounds_for_yesterday,
)


class _FakeBQClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.sql: str | None = None
        self.params: dict | None = None

    def execute_query(self, sql: str, params: dict) -> list[dict]:
        self.sql = sql
        self.params = params
        return self.rows


def test_sql_date_bounds_for_yesterday_returns_integer_bounds() -> None:
    start_int, end_int, partition_day = sql_date_bounds_for_yesterday(today=date(2026, 3, 19))

    assert start_int == 20260318
    assert end_int == 20260318
    assert partition_day == date(2026, 3, 18)


def test_fetch_events_projects_columns_and_partitions() -> None:
    sample_rows = [
        {
            "GLOBALEVENTID": 1,
            "SQLDATE": 20260318,
            "SOURCEURL": "https://example.com",
        }
    ]
    fake_client = _FakeBQClient(rows=sample_rows)

    result = fetch_events(
        bq_client=fake_client,  # type: ignore[arg-type]
        dataset="gdelt-bq.gdeltv2",
        partition_day=date(2026, 3, 18),
        sql_date=20260318,
    )

    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert fake_client.sql is not None
    assert "SELECT *" not in fake_client.sql.upper()
    assert "FROM `gdelt-bq.gdeltv2.events_partitioned`" in fake_client.sql
    assert "WHERE _PARTITIONDATE = @partition_date" in fake_client.sql
    assert "AND SQLDATE = @sql_date" in fake_client.sql
    assert "GLOBALEVENTID" in fake_client.sql
    assert "SOURCEURL" in fake_client.sql
    assert fake_client.params is not None
    assert set(fake_client.params.keys()) == {"partition_date", "sql_date"}


def test_parse_args_supports_date_and_backfill(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["daily_bq_pull.py", "--date", "2026-03-18", "--backfill-days", "3"],
    )
    args = parse_args()

    assert args.date == "2026-03-18"
    assert args.backfill_days == 3


def test_clean_v2_split_extracts_first_token_per_entity() -> None:
    raw = "ECONOMY,0.8;POLITICS,0.6;"

    assert clean_v2_split(raw) == ["ECONOMY", "POLITICS"]
    assert clean_v2_split(None) == []
