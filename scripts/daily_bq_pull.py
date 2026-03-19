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
    end_sql_date_exclusive = int(now.strftime("%Y%m%d"))
    return start_sql_date, end_sql_date_exclusive, partition_day


def build_enriched_partition_query(dataset: str, partition_day: date) -> str:
    """Build a partition-pruned JOIN query for Events, Mentions, and GKG."""
    # We use subqueries with partition filters to strictly limit scan costs.
    return f"""
        WITH daily_events AS (
            SELECT *
            FROM `{dataset}.events_partitioned`
            WHERE _PARTITIONDATE = @partition_date
              AND SQLDATE = @start_date
        ),
        daily_mentions AS (
            SELECT 
                GLOBALEVENTID,
                COUNT(*) as mentions_count,
                AVG(Confidence) as avg_confidence,
                APPROX_TOP_SUM(MentionIdentifier, 1, 1)[OFFSET(0)].value as top_mention_url
            FROM `{dataset}.eventmentions_partitioned`
            WHERE _PARTITIONDATE = @partition_date
            GROUP BY GLOBALEVENTID
        ),
        daily_gkg AS (
            SELECT 
                DocumentIdentifier,
                V2Themes as themes,
                V2Persons as persons,
                V2Organizations as organizations
            FROM `{dataset}.gkg_partitioned`
            WHERE _PARTITIONDATE = @partition_date
        )
        SELECT 
            e.*,
            m.mentions_count,
            m.avg_confidence,
            -- Extract themes/entities from GKG semicolon-delimited strings
            SPLIT(g.themes, ';') as themes,
            SPLIT(g.persons, ';') as persons,
            SPLIT(g.organizations, ';') as organizations
        FROM daily_events e
        LEFT JOIN daily_mentions m ON e.GLOBALEVENTID = m.GLOBALEVENTID
        LEFT JOIN daily_gkg g ON m.top_mention_url = g.DocumentIdentifier
    """


def fetch_partition_dataframe(
    bq_client: BigQueryClient,
    dataset: str,
    start_sql_date: int,
    partition_day: date,
) -> pd.DataFrame:
    """Execute the guarded enriched query and return a dataframe."""
    from google.cloud import bigquery

    sql = build_enriched_partition_query(dataset, partition_day)
    params = {
        "partition_date": bigquery.ScalarQueryParameter(
            "partition_date", "DATE", partition_day.isoformat()
        ),
        "start_date": bigquery.ScalarQueryParameter("start_date", "INT64", start_sql_date),
    }

    rows = bq_client.execute_query(sql, params)
    if not rows:
        return pd.DataFrame(columns=EVENTS_COLUMNS)

    # BigQuery returns arrays for themes/persons/orgs, pandas handles them as lists.
    df = pd.DataFrame(rows)
    
    # Ensure all expected columns exist
    for col in EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[EVENTS_COLUMNS]


def append_monthly_parquet(df: pd.DataFrame, hot_tier_path: str, partition_day: date) -> Path:
    """Append pulled rows into events_YYYYMM.parquet with dedupe by event id."""
    hot_tier_dir = Path(hot_tier_path)
    hot_tier_dir.mkdir(parents=True, exist_ok=True)

    out_file = hot_tier_dir / f"events_{partition_day.strftime('%Y%m')}.parquet"
    
    # Clean up themes/persons/orgs (strip offsets from V2GKG format e.g. "Theme,123")
    def clean_v2_list(items):
        if not isinstance(items, (list, tuple)): return []
        return [str(i).split(',')[0] for i in items if i]

    for col in ["themes", "persons", "organizations"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_v2_list)

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

    start_sql_date, _, partition_day = sql_date_bounds_for_yesterday()
    dataset = settings.gdelt_dataset

    df = fetch_partition_dataframe(
        bq_client=bq_client,
        dataset=dataset,
        start_sql_date=start_sql_date,
        partition_day=partition_day,
    )

    if df.empty:
        print(f"No rows returned for partition {start_sql_date}.")
        return None

    out_file = append_monthly_parquet(df, settings.hot_tier_path, partition_day)
    print(f"Daily enriched pull success: wrote {len(df)} rows to {out_file}")
    return out_file


if __name__ == "__main__":
    run_daily_pull()
