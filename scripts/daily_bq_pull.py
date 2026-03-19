"""Daily BigQuery ingestion job for GDELT Events, Mentions, and GKG hot tier.

This script pulls yesterday's partition from Events, Mentions, and GKG tables,
performs a local join in pandas to avoid BigQuery timeout/complexity issues,
and appends the result to monthly Parquet files.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

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
    "themes",
    "persons",
    "organizations",
    "mentions_count",
    "avg_confidence",
]


def sql_date_bounds_for_yesterday(today: date | None = None) -> tuple[int, int, date]:
    """Return inclusive/exclusive SQLDATE bounds for yesterday's partition."""
    now = today or date.today()
    partition_day = now - timedelta(days=1)
    start_sql_date = int(partition_day.strftime("%Y%m%d"))
    return start_sql_date, start_sql_date, partition_day


def fetch_events(bq_client: BigQueryClient, dataset: str, partition_day: date, sql_date: int) -> pd.DataFrame:
    print(f"Fetching Events for {sql_date}...")
    # Explicitly project only the columns we need from Events table
    event_cols = [
        "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year",
        "Actor1CountryCode", "Actor2CountryCode", "Actor1Type1Code", "Actor2Type1Code",
        "EventCode", "EventBaseCode", "EventRootCode", "QuadClass",
        "GoldsteinScale", "NumMentions", "NumSources", "AvgTone",
        "Actor1Geo_CountryCode", "Actor2Geo_CountryCode", "ActionGeo_CountryCode",
        "ActionGeo_Lat", "ActionGeo_Long", "SOURCEURL"
    ]
    projected = ", ".join(event_cols)
    sql = f"""
        SELECT {projected}
        FROM `{dataset}.events_partitioned`
        WHERE _PARTITIONDATE = @partition_date
          AND SQLDATE = @sql_date
    """
    params = {
        "partition_date": bigquery.ScalarQueryParameter("partition_date", "DATE", partition_day.isoformat()),
        "sql_date": bigquery.ScalarQueryParameter("sql_date", "INT64", sql_date),
    }
    rows = bq_client.execute_query(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_mentions_agg(bq_client: BigQueryClient, dataset: str, partition_day: date) -> pd.DataFrame:
    print(f"Fetching and aggregating Mentions for {partition_day}...")
    sql = f"""
        SELECT 
            GLOBALEVENTID,
            COUNT(*) as mentions_count,
            AVG(Confidence) as avg_confidence,
            APPROX_TOP_SUM(MentionIdentifier, 1, 1)[OFFSET(0)].value as top_mention_url
        FROM `{dataset}.eventmentions_partitioned`
        WHERE _PARTITIONDATE = @partition_date
        GROUP BY GLOBALEVENTID
    """
    params = {
        "partition_date": bigquery.ScalarQueryParameter("partition_date", "DATE", partition_day.isoformat()),
    }
    rows = bq_client.execute_query(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_gkg_data(bq_client: BigQueryClient, dataset: str, partition_day: date) -> pd.DataFrame:
    print(f"Fetching GKG entities for {partition_day}...")
    # GKG is large, we only pull what we need
    sql = f"""
        SELECT 
            DocumentIdentifier,
            V2Themes as themes_raw,
            V2Persons as persons_raw,
            V2Organizations as organizations_raw
        FROM `{dataset}.gkg_partitioned`
        WHERE _PARTITIONDATE = @partition_date
    """
    params = {
        "partition_date": bigquery.ScalarQueryParameter("partition_date", "DATE", partition_day.isoformat()),
    }
    rows = bq_client.execute_query(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def clean_v2_split(val):
    if not isinstance(val, str) or not val: return []
    return [i.split(',')[0] for i in val.split(';') if i]


def run_daily_pull() -> Path | None:
    settings = Settings()
    bq_client = BigQueryClient(settings)
    sql_date, _, partition_day = sql_date_bounds_for_yesterday()
    dataset = settings.gdelt_dataset

    # 1. Fetch data in parallel-ish (sequentially but simple queries)
    events_df = fetch_events(bq_client, dataset, partition_day, sql_date)
    if events_df.empty:
        print("No events found for yesterday.")
        return None

    mentions_df = fetch_mentions_agg(bq_client, dataset, partition_day)
    gkg_df = fetch_gkg_data(bq_client, dataset, partition_day)

    print("Merging and enriching data locally...")
    # 2. Local JOIN
    df = events_df.merge(mentions_df, on="GLOBALEVENTID", how="left")
    
    if not gkg_df.empty:
        df = df.merge(gkg_df, left_on="top_mention_url", right_on="DocumentIdentifier", how="left")
        print("Cleaning GKG lists...")
        df["themes"] = df["themes_raw"].apply(clean_v2_split)
        df["persons"] = df["persons_raw"].apply(clean_v2_split)
        df["organizations"] = df["organizations_raw"].apply(clean_v2_split)
    else:
        df["themes"] = [[]] * len(df)
        df["persons"] = [[]] * len(df)
        df["organizations"] = [[]] * len(df)

    # 3. Finalize schema
    for col in EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    final_df = df[EVENTS_COLUMNS].copy()
    
    # 4. Write Parquet
    hot_tier_dir = Path(settings.hot_tier_path)
    hot_tier_dir.mkdir(parents=True, exist_ok=True)
    out_file = hot_tier_dir / f"events_{partition_day.strftime('%Y%m')}.parquet"
    
    if out_file.exists():
        print(f"Appending to existing file {out_file}...")
        existing = pd.read_parquet(out_file)
        final_df = pd.concat([existing, final_df], ignore_index=True)
    
    final_df = final_df.drop_duplicates(subset=["GLOBALEVENTID"], keep="last")
    final_df.to_parquet(out_file, index=False)
    
    print(f"Success: Wrote {len(final_df)} enriched rows to {out_file}")
    return out_file


if __name__ == "__main__":
    run_daily_pull()
