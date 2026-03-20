"""Daily BigQuery ingestion job for GDELT Events, Mentions, and GKG hot tier.

This script pulls yesterday's partition from Events, Mentions, and GKG tables,
performs a local join in pandas to avoid BigQuery timeout/complexity issues,
and appends the result to monthly Parquet files.
"""

from __future__ import annotations

import argparse
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
        help="Pull the last N days (max 7). Runs one day at a time.",
    )
    return parser.parse_args()


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


def fetch_mentions_agg(
    bq_client: BigQueryClient, dataset: str, partition_day: date
) -> pd.DataFrame:
    print(f"Fetching Mentions for {partition_day}...")
    sql = f"""
        SELECT
            GLOBALEVENTID,
            COUNT(*)        AS mentions_count,
            AVG(Confidence) AS avg_confidence,
            ARRAY_AGG(MentionIdentifier IGNORE NULLS LIMIT 5) AS mention_urls
        FROM `{dataset}.eventmentions_partitioned`
        WHERE _PARTITIONDATE = @partition_date
        GROUP BY GLOBALEVENTID
    """
    params = {
        "partition_date": bigquery.ScalarQueryParameter(
            "partition_date", "DATE", partition_day.isoformat()
        ),
    }
    rows = bq_client.execute_query(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_gkg_data(
    bq_client: BigQueryClient,
    dataset: str,
    partition_day: date,
    source_urls: list[str],          # ← only fetch GKG for URLs we actually have
) -> pd.DataFrame:
    if not source_urls:
        return pd.DataFrame()

    print(f"Fetching GKG for {len(source_urls)} known source URLs...")

    # Build a VALUES literal — BigQuery supports up to ~10k values inline
    # Truncate to 5000 URLs to stay well within query size limits
    urls_sample = source_urls[:5000]
    url_list = ", ".join(f"'{u.replace(chr(39), '')}'" for u in urls_sample)

    sql = f"""
        SELECT
            DocumentIdentifier,
            V2Themes    AS themes_raw,
            V2Persons   AS persons_raw,
            V2Organizations AS organizations_raw
        FROM `{dataset}.gkg_partitioned`
        WHERE _PARTITIONDATE = @partition_date
          AND DocumentIdentifier IN ({url_list})
    """
    params = {
        "partition_date": bigquery.ScalarQueryParameter(
            "partition_date", "DATE", partition_day.isoformat()
        ),
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

    # Extract all mention URLs as GKG join candidates
    # Each event has up to 5 mention URLs — explode them all
    mention_urls = (
        mentions_df["mention_urls"]
        .dropna()
        .explode()
        .dropna()
        .unique()
        .tolist()
    )
    source_urls = events_df["SOURCEURL"].dropna().unique().tolist()
    all_urls = list(set(source_urls + mention_urls))[:5000]

    gkg_df = fetch_gkg_data(bq_client, dataset, partition_day, all_urls)

    print("Merging and enriching data locally...")
    # 2. Local JOIN
    # Merge events + mentions
    df = events_df.merge(mentions_df, on="GLOBALEVENTID", how="left")

    # Merge GKG on SOURCEURL (not top_mention_url)
    if not gkg_df.empty:
        # Build URL → themes/persons/orgs lookup
        gkg_lookup = {}
        for _, row in gkg_df.iterrows():
            gkg_lookup[row["DocumentIdentifier"]] = row

        def enrich_event(row):
            # Try SOURCEURL first, then any mention URL
            candidates = [row.get("SOURCEURL")] + (row.get("mention_urls") or [])
            for url in candidates:
                if url and url in gkg_lookup:
                    return gkg_lookup[url]
            return None

        gkg_matches = df.apply(enrich_event, axis=1)
        df["themes"]        = gkg_matches.apply(lambda r: clean_v2_split(r["themes_raw"])        if r is not None else [])
        df["persons"]       = gkg_matches.apply(lambda r: clean_v2_split(r["persons_raw"])       if r is not None else [])
        df["organizations"] = gkg_matches.apply(lambda r: clean_v2_split(r["organizations_raw"]) if r is not None else [])

    else:
        df["themes"]        = [[] for _ in range(len(df))]
        df["persons"]       = [[] for _ in range(len(df))]
        df["organizations"] = [[] for _ in range(len(df))]

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


def run_for_date(target_date: date) -> None:
    """Run the daily pull for a specific date."""
    settings = Settings()
    bq_client = BigQueryClient(settings)
    dataset = settings.gdelt_dataset

    partition_day = target_date
    sql_date = int(partition_day.strftime("%Y%m%d"))

    print(f"\n=== Pulling data for {partition_day} ===")

    events_df = fetch_events(bq_client, dataset, partition_day, sql_date)
    if events_df.empty:
        print(f"No events found for {partition_day}, skipping.")
        return

    mentions_df = fetch_mentions_agg(bq_client, dataset, partition_day)

    mention_urls = (
        mentions_df["mention_urls"]
        .dropna()
        .explode()
        .dropna()
        .unique()
        .tolist()
    ) if "mention_urls" in mentions_df.columns else []

    source_urls = events_df["SOURCEURL"].dropna().unique().tolist()
    all_urls = list(set(source_urls + mention_urls))[:5000]

    gkg_df = fetch_gkg_data(bq_client, dataset, partition_day, all_urls)

    print("Merging and enriching data locally...")
    df = events_df.merge(mentions_df[["GLOBALEVENTID", "mentions_count", "avg_confidence"]], on="GLOBALEVENTID", how="left")

    if not gkg_df.empty:
        gkg_lookup = {
            row["DocumentIdentifier"]: row
            for _, row in gkg_df.iterrows()
        }

        def enrich_event(row):
            candidates = [row.get("SOURCEURL")] + (row.get("mention_urls") or [])
            for url in candidates:
                if url and url in gkg_lookup:
                    return gkg_lookup[url]
            return None

        gkg_matches = df.apply(enrich_event, axis=1)
        df["themes"]        = gkg_matches.apply(lambda r: clean_v2_split(r["themes_raw"])        if r is not None else [])
        df["persons"]       = gkg_matches.apply(lambda r: clean_v2_split(r["persons_raw"])       if r is not None else [])
        df["organizations"] = gkg_matches.apply(lambda r: clean_v2_split(r["organizations_raw"]) if r is not None else [])
    else:
        df["themes"]        = [[] for _ in range(len(df))]
        df["persons"]       = [[] for _ in range(len(df))]
        df["organizations"] = [[] for _ in range(len(df))]

    for col in EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None

    final_df = df[EVENTS_COLUMNS].copy()

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


if __name__ == "__main__":
    args = parse_args()

    if args.backfill_days is not None:
        days = min(args.backfill_days, 7)  # hard cap at 7
        print(f"Backfilling last {days} days...")
        for i in range(days, 0, -1):  # oldest first
            target = date.today() - timedelta(days=i)
            run_for_date(target)
        print("\nBackfill complete.")

    elif args.date is not None:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            print(f"Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            exit(1)
        # Hard cap — don't allow pulling more than 7 days back
        if (date.today() - target).days > 7:
            print(f"Error: --date cannot be more than 7 days in the past.")
            exit(1)
        run_for_date(target)

    else:
        # Default: yesterday
        run_for_date(date.today() - timedelta(days=1))
