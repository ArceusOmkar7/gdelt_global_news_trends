"""Daily BigQuery ingestion job for GDELT Events hot tier.

This script pulls only yesterday's Events partition, enforces dry-run scan
budget via the shared BigQuery client, and appends the result to monthly
Parquet files under HOT_TIER_PATH.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from backend.infrastructure.config.settings import Settings
from backend.infrastructure.data_access.bigquery_client import BigQueryClient

EVENTS_COLUMNS: list[str] = [
    "GLOBALEVENTID",
    "SQLDATE",
    "MonthYear",
    "Year",
    "Actor1CountryCode",
    "Actor2CountryCode",
    "Actor1Type1Code",
    "Actor2Type1Code",
    "EventCode",
    "EventBaseCode",
    "EventRootCode",
    "QuadClass",
    "GoldsteinScale",
    "NumMentions",
    "NumSources",
    "AvgTone",
    "Actor1Geo_CountryCode",
    "Actor2Geo_CountryCode",
    "ActionGeo_CountryCode",
    "ActionGeo_Lat",
    "ActionGeo_Long",
    "SOURCEURL",
]


def sql_date_bounds_for_yesterday(today: date | None = None) -> tuple[int, int, date]:
    """Return inclusive/exclusive SQLDATE bounds for yesterday's partition."""
    now = today or date.today()
    partition_day = now - timedelta(days=1)
    start_sql_date = int(partition_day.strftime("%Y%m%d"))
    end_sql_date_exclusive = int(now.strftime("%Y%m%d"))
    return start_sql_date, end_sql_date_exclusive, partition_day


def build_events_partition_query(table_fqn: str) -> str:
    """Build a partition-pruned Events query with explicit column projection."""
    projected = ",\n                ".join(EVENTS_COLUMNS)
    return f"""
        SELECT
                {projected}
        FROM `{table_fqn}`
                WHERE _PARTITIONDATE = @partition_date
                    AND SQLDATE >= @start_date
                    AND SQLDATE < @end_date_exclusive
    """


def fetch_partition_dataframe(
    bq_client: BigQueryClient,
    table_fqn: str,
    start_sql_date: int,
    end_sql_date_exclusive: int,
    partition_day: date,
) -> pd.DataFrame:
    """Execute the guarded query and return a dataframe."""
    from google.cloud import bigquery

    sql = build_events_partition_query(table_fqn)
    params = {
        "partition_date": bigquery.ScalarQueryParameter(
            "partition_date", "DATE", partition_day.isoformat()
        ),
        "start_date": bigquery.ScalarQueryParameter("start_date", "INT64", start_sql_date),
        "end_date_exclusive": bigquery.ScalarQueryParameter(
            "end_date_exclusive", "INT64", end_sql_date_exclusive
        ),
    }

    rows = bq_client.execute_query(sql, params)
    if not rows:
        return pd.DataFrame(columns=EVENTS_COLUMNS)

    df = pd.DataFrame(rows)
    for col in EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Keep stable schema order for downstream parquet readers.
    return df[EVENTS_COLUMNS]


def append_monthly_parquet(df: pd.DataFrame, hot_tier_path: str, partition_day: date) -> Path:
    """Append pulled rows into events_YYYYMM.parquet with dedupe by event id."""
    hot_tier_dir = Path(hot_tier_path)
    hot_tier_dir.mkdir(parents=True, exist_ok=True)

    out_file = hot_tier_dir / f"events_{partition_day.strftime('%Y%m')}.parquet"
    if out_file.exists():
        existing_df = pd.read_parquet(out_file)
        combined = pd.concat([existing_df, df], ignore_index=True)
    else:
        combined = df.copy()

    if "GLOBALEVENTID" in combined.columns:
        combined = combined.drop_duplicates(subset=["GLOBALEVENTID"], keep="last")

    combined.to_parquet(out_file, index=False)
    return out_file


def run_daily_pull() -> Path | None:
    """Run the daily ingestion process and return output parquet path if written."""
    settings = Settings()
    bq_client = BigQueryClient(settings)

    start_sql_date, end_sql_date_exclusive, partition_day = sql_date_bounds_for_yesterday()
    table_name = settings.gdelt_table
    if not table_name.endswith("_partitioned"):
        table_name = f"{table_name}_partitioned"
    table_fqn = f"{settings.gdelt_dataset}.{table_name}"

    df = fetch_partition_dataframe(
        bq_client=bq_client,
        table_fqn=table_fqn,
        start_sql_date=start_sql_date,
        end_sql_date_exclusive=end_sql_date_exclusive,
        partition_day=partition_day,
    )

    if df.empty:
        print(
            "No rows returned for partition",
            start_sql_date,
            "(dry-run guard still applied).",
        )
        return None

    out_file = append_monthly_parquet(df, settings.hot_tier_path, partition_day)
    print(f"Daily pull success: wrote {len(df)} rows to {out_file}")
    return out_file


if __name__ == "__main__":
    run_daily_pull()
