from datetime import date

import pandas as pd

from scripts.daily_bq_pull import (
    EVENTS_COLUMNS,
    append_monthly_parquet,
    build_events_partition_query,
    sql_date_bounds_for_yesterday,
)


def test_build_events_partition_query_is_pruned_and_projected() -> None:
    sql = build_events_partition_query("gdelt-bq.gdeltv2.events")

    assert "SELECT *" not in sql.upper()
    for col in EVENTS_COLUMNS:
        assert col in sql
    assert "SQLDATE >= @start_date" in sql
    assert "SQLDATE < @end_date_exclusive" in sql


def test_sql_date_bounds_for_yesterday_returns_integer_bounds() -> None:
    start_int, end_int, partition_day = sql_date_bounds_for_yesterday(today=date(2026, 3, 19))

    assert start_int == 20260318
    assert end_int == 20260319
    assert partition_day == date(2026, 3, 18)


def test_append_monthly_parquet_dedupes_global_event_id(tmp_path) -> None:
    base_df = pd.DataFrame(
        [
            {"GLOBALEVENTID": 1, "SQLDATE": 20260318, "SOURCEURL": "a"},
            {"GLOBALEVENTID": 2, "SQLDATE": 20260318, "SOURCEURL": "b"},
        ]
    )
    for col in EVENTS_COLUMNS:
        if col not in base_df.columns:
            base_df[col] = None
    base_df = base_df[EVENTS_COLUMNS]

    new_df = pd.DataFrame(
        [
            {"GLOBALEVENTID": 2, "SQLDATE": 20260318, "SOURCEURL": "b2"},
            {"GLOBALEVENTID": 3, "SQLDATE": 20260318, "SOURCEURL": "c"},
        ]
    )
    for col in EVENTS_COLUMNS:
        if col not in new_df.columns:
            new_df[col] = None
    new_df = new_df[EVENTS_COLUMNS]

    out = append_monthly_parquet(base_df, str(tmp_path), date(2026, 3, 18))
    assert out.exists()

    out = append_monthly_parquet(new_df, str(tmp_path), date(2026, 3, 18))
    merged = pd.read_parquet(out)

    assert set(merged["GLOBALEVENTID"].tolist()) == {1, 2, 3}
    latest_for_2 = merged.loc[merged["GLOBALEVENTID"] == 2, "SOURCEURL"].iloc[0]
    assert latest_for_2 == "b2"
