"""15-minute realtime ingestion job for GDELT Events CSV feed.

This script reads lastupdate.txt, pulls the latest Events CSV zip, projects
only approved Events columns, deduplicates by GLOBALEVENTID against recent
hot-tier rows, and appends to realtime_buffer.parquet.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from backend.infrastructure.config.settings import Settings

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

# GDELT Events 2.1 CSV positional indexes.
COLUMN_INDEX: dict[str, int] = {
    "GLOBALEVENTID": 0,
    "SQLDATE": 1,
    "MonthYear": 2,
    "Year": 3,
    "Actor1CountryCode": 7,
    "Actor2CountryCode": 17,
    "Actor1Type1Code": 12,
    "Actor2Type1Code": 22,
    "EventCode": 26,
    "EventBaseCode": 27,
    "EventRootCode": 28,
    "QuadClass": 29,
    "GoldsteinScale": 30,
    "NumMentions": 31,
    "NumSources": 32,
    "AvgTone": 34,
    "Actor1Geo_CountryCode": 37,
    "Actor2Geo_CountryCode": 44,
    "ActionGeo_CountryCode": 51,
    "ActionGeo_Lat": 53,
    "ActionGeo_Long": 54,
    "SOURCEURL": 57,
}

NUMERIC_COLUMNS = {
    "GLOBALEVENTID",
    "SQLDATE",
    "MonthYear",
    "Year",
    "QuadClass",
    "GoldsteinScale",
    "NumMentions",
    "NumSources",
    "AvgTone",
    "ActionGeo_Lat",
    "ActionGeo_Long",
}


def parse_lastupdate_events_url(lastupdate_text: str) -> str:
    """Extract the latest Events export URL from lastupdate.txt content."""
    for raw_line in lastupdate_text.strip().splitlines():
        line = raw_line.strip()
        if "export.CSV" in line:
            parts = line.split()
            if parts:
                return parts[-1]
    raise ValueError("Could not find Events export.CSV URL in lastupdate.txt")


def fetch_latest_events_zip_bytes(timeout: int = 20) -> bytes:
    """Download latest Events zip bytes from the GDELT lastupdate feed."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt")
        r.raise_for_status()
        events_url = parse_lastupdate_events_url(r.text)

        z = client.get(events_url)
        z.raise_for_status()
        return z.content


def parse_events_zip_to_dataframe(zipped_events_csv: bytes) -> pd.DataFrame:
    """Parse zipped Events TSV and project approved columns only."""
    with zipfile.ZipFile(io.BytesIO(zipped_events_csv)) as archive:
        names = archive.namelist()
        if not names:
            return pd.DataFrame(columns=EVENTS_COLUMNS)

        with archive.open(names[0]) as handle:
            raw_df = pd.read_csv(
                handle,
                sep="\t",
                header=None,
                dtype=str,
                low_memory=False,
            )

    projected: dict[str, pd.Series] = {}
    for col in EVENTS_COLUMNS:
        idx = COLUMN_INDEX[col]
        if idx < raw_df.shape[1]:
            projected[col] = raw_df.iloc[:, idx]
        else:
            projected[col] = pd.Series([None] * len(raw_df))

    df = pd.DataFrame(projected)

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["GLOBALEVENTID", "SQLDATE"])
    return df[EVENTS_COLUMNS]


def load_recent_event_ids(hot_tier_path: str, max_rows: int = 1000) -> set[int]:
    """Load up to max_rows recent event ids from local hot-tier parquet files."""
    hot_dir = Path(hot_tier_path)
    parquet_files = list(hot_dir.glob("*.parquet"))
    if not parquet_files:
        return set()

    glob_path = str(hot_dir / "*.parquet")
    conn = duckdb.connect(database=":memory:")
    try:
        rows = conn.execute(
            f"""
            SELECT CAST(GLOBALEVENTID AS BIGINT) AS event_id
            FROM read_parquet('{glob_path}')
            WHERE GLOBALEVENTID IS NOT NULL
            ORDER BY SQLDATE DESC
            LIMIT ?
            """,
            [max_rows],
        ).fetchall()
        return {int(row[0]) for row in rows if row and row[0] is not None}
    finally:
        conn.close()


def dedupe_against_recent(df: pd.DataFrame, recent_ids: set[int]) -> pd.DataFrame:
    """Drop incoming rows that already exist in recent hot-tier history."""
    if df.empty or not recent_ids:
        return df
    mask = ~df["GLOBALEVENTID"].astype("int64").isin(recent_ids)
    return df.loc[mask].copy()


def append_realtime_buffer(df: pd.DataFrame, hot_tier_path: str) -> Path:
    """Append deduped rows to realtime_buffer.parquet and dedupe within buffer."""
    hot_dir = Path(hot_tier_path)
    hot_dir.mkdir(parents=True, exist_ok=True)

    buffer_file = hot_dir / "realtime_buffer.parquet"
    if buffer_file.exists():
        current = pd.read_parquet(buffer_file)
        merged = pd.concat([current, df], ignore_index=True)
    else:
        merged = df.copy()

    if "GLOBALEVENTID" in merged.columns:
        merged = merged.drop_duplicates(subset=["GLOBALEVENTID"], keep="last")

    merged.to_parquet(buffer_file, index=False)
    return buffer_file


def run_realtime_fetch() -> Path | None:
    """Run the realtime ingestion process and return output file when written."""
    settings = Settings()

    zip_bytes = fetch_latest_events_zip_bytes()
    incoming_df = parse_events_zip_to_dataframe(zip_bytes)
    if incoming_df.empty:
        print("Realtime fetch returned 0 parsed rows.")
        return None

    recent_ids = load_recent_event_ids(settings.hot_tier_path, max_rows=1000)
    new_df = dedupe_against_recent(incoming_df, recent_ids)
    if new_df.empty:
        print("Realtime fetch had no new rows after dedupe.")
        return None

    out_file = append_realtime_buffer(new_df, settings.hot_tier_path)
    print(f"Realtime fetch success: appended {len(new_df)} new rows to {out_file}")
    return out_file


if __name__ == "__main__":
    run_realtime_fetch()
