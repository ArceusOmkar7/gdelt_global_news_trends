"""Daily BigQuery ingestion job for GDELT Events, Mentions, and GKG hot tier.

This script pulls data from Events, Mentions, and GKG tables using a single
optimized BigQuery JOIN. Results are saved as daily Parquet files to ensure
ingestion time remains constant throughout the month. Supports parallel backfills.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from backend.infrastructure.config.settings import settings
from backend.infrastructure.data_access.bigquery_client import BigQueryClient
from backend.infrastructure.services.lookup_service import lookup_service

# Final column order for the hot tier
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull one day of GDELT data into the hot tier."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to pull in YYYY-MM-DD format. Defaults to yesterday.",
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=None,
        help="Pull the last N days (max 14).",
    )
    parser.add_argument(
        "--start-offset",
        type=int,
        default=1,
        help="Start backfill N days ago (default 1 = yesterday).",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run backfill days in parallel.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3).",
    )
    return parser.parse_args()


def fetch_enriched_data(
    bq_client: BigQueryClient, dataset: str, partition_day: date, sql_date: int
) -> pd.DataFrame:
    """Fetch events joined with mentions and GKG data in a single query."""
    print(f"Fetching enriched GDELT data for {partition_day} (SQLDATE={sql_date})...")

    # This query performs a server-side join across three partitioned tables.
    # We use ARRAY_AGG + UNNEST logic to clean GKG themes/persons/orgs in SQL.
    sql = f"""
        WITH events AS (
          SELECT
            GLOBALEVENTID, SQLDATE, MonthYear, Year,
            Actor1CountryCode, Actor2CountryCode, Actor1Type1Code, Actor2Type1Code,
            EventCode, EventBaseCode, EventRootCode, QuadClass,
            GoldsteinScale, NumMentions, NumSources, AvgTone,
            Actor1Geo_CountryCode, Actor2Geo_CountryCode, ActionGeo_CountryCode,
            ActionGeo_Lat, ActionGeo_Long, SOURCEURL
          FROM `{dataset}.events_partitioned`
          WHERE _PARTITIONDATE = @partition_date
            AND SQLDATE = @sql_date
        ),
        mentions AS (
          SELECT
            GLOBALEVENTID,
            COUNT(*) AS mentions_count,
            AVG(Confidence) AS avg_confidence
          FROM `{dataset}.eventmentions_partitioned`
          WHERE _PARTITIONDATE = @partition_date
          GROUP BY GLOBALEVENTID
        ),
        gkg AS (
          SELECT
            DocumentIdentifier,
            ARRAY(
                SELECT DISTINCT SPLIT(item, ',')[OFFSET(0)]
                FROM UNNEST(SPLIT(V2Themes, ';')) AS item
                WHERE item != ''
            ) AS themes,
            ARRAY(
                SELECT DISTINCT SPLIT(item, ',')[OFFSET(0)]
                FROM UNNEST(SPLIT(V2Persons, ';')) AS item
                WHERE item != ''
            ) AS persons,
            ARRAY(
                SELECT DISTINCT SPLIT(item, ',')[OFFSET(0)]
                FROM UNNEST(SPLIT(V2Organizations, ';')) AS item
                WHERE item != ''
            ) AS organizations
          FROM `{dataset}.gkg_partitioned`
          WHERE _PARTITIONDATE = @partition_date
        )
        SELECT
          e.*,
          COALESCE(m.mentions_count, 0) AS mentions_count,
          m.avg_confidence,
          COALESCE(g.themes, []) AS themes,
          COALESCE(g.persons, []) AS persons,
          COALESCE(g.organizations, []) AS organizations
        FROM events e
        LEFT JOIN mentions m ON e.GLOBALEVENTID = m.GLOBALEVENTID
        LEFT JOIN gkg g ON e.SOURCEURL = g.DocumentIdentifier
    """
    
    params = {
        "partition_date": bigquery.ScalarQueryParameter("partition_date", "DATE", partition_day.isoformat()),
        "sql_date": bigquery.ScalarQueryParameter("sql_date", "INT64", sql_date),
    }

    rows = bq_client.execute_query(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def cleanup_realtime_buffer(target_date: date, settings: settings) -> None:
    """Remove records for the processed date from the realtime buffer to prevent duplicates."""
    hot_tier_dir = Path(settings.hot_tier_path)
    buffer_file = hot_tier_dir / "realtime_buffer.parquet"
    
    if not buffer_file.exists():
        return

    print(f"Cleaning up {target_date} from realtime_buffer.parquet...")
    try:
        df = pd.read_parquet(buffer_file)
        sql_date = int(target_date.strftime("%Y%m%d"))
        
        if "SQLDATE" in df.columns:
            # Keep only records that are NOT for the date we just pulled from BQ
            original_len = len(df)
            df = df[df["SQLDATE"] != sql_date]
            
            if len(df) < original_len:
                if df.empty:
                    buffer_file.unlink()
                    print("Buffer empty after cleanup, removed file.")
                else:
                    df.to_parquet(buffer_file, index=False)
                    print(f"Removed {original_len - len(df)} records from buffer.")
            else:
                print("No matching records found in buffer.")
    except Exception as e:
        print(f"Warning: Failed to cleanup realtime buffer: {e}")


def run_for_date(target_date: date) -> Path | None:
    """Run the ingestion for a specific date and save to a daily Parquet file."""
    # Use global settings instance
    bq_client = BigQueryClient(settings)
    dataset = settings.gdelt_dataset

    sql_date = int(target_date.strftime("%Y%m%d"))
    
    start_time = time.monotonic()
    df = fetch_enriched_data(bq_client, dataset, target_date, sql_date)
    
    if df.empty:
        print(f"No data found for {target_date}, skipping.")
        return None

    # Ensure all required columns exist and are in the correct order
    for col in EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    final_df = df[EVENTS_COLUMNS].copy()
    
    # Save to daily file instead of monthly rollup
    hot_tier_dir = Path(settings.hot_tier_path)
    hot_tier_dir.mkdir(parents=True, exist_ok=True)
    out_file = hot_tier_dir / f"events_{target_date.strftime('%Y%m%d')}.parquet"
    
    final_df.to_parquet(out_file, index=False)
    
    # Cleanup buffer to avoid duplicates across files
    cleanup_realtime_buffer(target_date, settings)
    
    elapsed = time.monotonic() - start_time
    print(f"Success: Wrote {len(final_df)} rows to {out_file} in {elapsed:.1f}s")
    return out_file


if __name__ == "__main__":
    args = parse_args()

    # Ensure lookups are available and fresh
    print("Refreshing GDELT country lookups...")
    lookup_service.refresh_country_codes()

    if args.backfill_days is not None:
        days = min(args.backfill_days, 14)
        start_offset = args.start_offset
        targets = [date.today() - timedelta(days=i) for i in range(start_offset + days - 1, start_offset - 1, -1)]
        
        print(f"Backfilling {len(targets)} days (parallel={args.parallel}, workers={args.workers})...")
        
        if args.parallel:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(run_for_date, t): t for t in targets}
                for future in as_completed(futures):
                    target = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        print(f"Error backfilling {target}: {exc}")
        else:
            for target in targets:
                run_for_date(target)
                
        print("\nBackfill complete.")

    elif args.date is not None:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            print(f"Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            exit(1)
        
        run_for_date(target)

    else:
        # Default: yesterday
        run_for_date(date.today() - timedelta(days=1))
