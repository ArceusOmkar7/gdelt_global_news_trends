"""Nightly AI precompute job for forecasts and country briefings.

This script reads hot-tier parquet data and produces:
1) CACHE_PATH/forecasts.parquet (30-day predictions for top countries)
2) CACHE_PATH/briefings.json (country-level briefing text cache)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from backend.domain.models.event import EventCountByDate
from backend.domain.services.forecasting_service import ForecastingService
from backend.infrastructure.config.settings import Settings


def sql_date_int(d: date) -> int:
    """Convert date to SQLDATE integer format (YYYYMMDD)."""
    return int(d.strftime("%Y%m%d"))


def top_countries_by_volume(
    conn: duckdb.DuckDBPyConnection,
    parquet_glob: str,
    start_sql_date: int,
    end_sql_date_exclusive: int,
    limit: int,
) -> list[str]:
    """Get top countries by ActionGeo event volume in given window."""
    rows = conn.execute(
        f"""
        SELECT
            ActionGeo_CountryCode AS country_code,
            COUNT(*) AS event_count
        FROM read_parquet('{parquet_glob}')
        WHERE SQLDATE >= ?
          AND SQLDATE < ?
          AND ActionGeo_CountryCode IS NOT NULL
          AND ActionGeo_CountryCode <> ''
        GROUP BY ActionGeo_CountryCode
        ORDER BY event_count DESC
        LIMIT ?
        """,
        [start_sql_date, end_sql_date_exclusive, limit],
    ).fetchall()
    return [str(row[0]) for row in rows if row and row[0]]


def fetch_conflict_daily_counts(
    conn: duckdb.DuckDBPyConnection,
    parquet_glob: str,
    country_code: str,
    start_sql_date: int,
    end_sql_date_exclusive: int,
) -> list[EventCountByDate]:
    """Get daily conflict counts (QuadClass 3/4) for forecasting."""
    rows = conn.execute(
        f"""
        SELECT
            SQLDATE,
            COUNT(*) AS event_count,
            AVG(GoldsteinScale) AS avg_goldstein,
            SUM(NumMentions) AS total_mentions,
            AVG(AvgTone) AS avg_tone
        FROM read_parquet('{parquet_glob}')
        WHERE SQLDATE >= ?
          AND SQLDATE < ?
          AND ActionGeo_CountryCode = ?
          AND QuadClass IN (3, 4)
        GROUP BY SQLDATE
        ORDER BY SQLDATE ASC
        """,
        [start_sql_date, end_sql_date_exclusive, country_code],
    ).fetchall()

    out: list[EventCountByDate] = []
    for sql_date_raw, event_count, avg_goldstein, total_mentions, avg_tone in rows:
        sql_date_str = str(int(sql_date_raw))
        parsed_date = date(
            int(sql_date_str[:4]),
            int(sql_date_str[4:6]),
            int(sql_date_str[6:8]),
        )
        out.append(
            EventCountByDate(
                date=parsed_date,
                count=int(event_count),
                avg_goldstein_scale=(float(avg_goldstein) if avg_goldstein is not None else None),
                total_mentions=int(total_mentions or 0),
                avg_tone=(float(avg_tone) if avg_tone is not None else None),
            )
        )
    return out


def build_country_event_summary(
    conn: duckdb.DuckDBPyConnection,
    parquet_glob: str,
    country_code: str,
    start_sql_date: int,
    end_sql_date_exclusive: int,
) -> str:
    """Build a compact factual summary for a country's recent events."""
    metrics = conn.execute(
        f"""
        SELECT
            COUNT(*) AS event_count,
            AVG(GoldsteinScale) AS avg_goldstein,
            AVG(AvgTone) AS avg_tone,
            SUM(NumMentions) AS total_mentions,
            SUM(NumSources) AS total_sources
        FROM read_parquet('{parquet_glob}')
        WHERE SQLDATE >= ?
          AND SQLDATE < ?
          AND ActionGeo_CountryCode = ?
        """,
        [start_sql_date, end_sql_date_exclusive, country_code],
    ).fetchone()

    top_codes = conn.execute(
        f"""
        SELECT EventRootCode, COUNT(*) AS c
        FROM read_parquet('{parquet_glob}')
        WHERE SQLDATE >= ?
          AND SQLDATE < ?
          AND ActionGeo_CountryCode = ?
          AND EventRootCode IS NOT NULL
          AND EventRootCode <> ''
        GROUP BY EventRootCode
        ORDER BY c DESC
        LIMIT 5
        """,
        [start_sql_date, end_sql_date_exclusive, country_code],
    ).fetchall()

    event_count = int(metrics[0] or 0) if metrics else 0
    avg_goldstein = float(metrics[1]) if metrics and metrics[1] is not None else 0.0
    avg_tone = float(metrics[2]) if metrics and metrics[2] is not None else 0.0
    total_mentions = int(metrics[3] or 0) if metrics else 0
    total_sources = int(metrics[4] or 0) if metrics else 0
    top_event_codes = [str(row[0]) for row in top_codes if row and row[0]]

    return (
        f"Country {country_code}. "
        f"Recent events: {event_count}. "
        f"Avg Goldstein: {avg_goldstein:.2f}. "
        f"Avg tone: {avg_tone:.2f}. "
        f"Total mentions: {total_mentions}. "
        f"Total sources: {total_sources}. "
        f"Top root codes: {', '.join(top_event_codes) if top_event_codes else 'n/a'}."
    )


def fallback_briefing(country_code: str, summary: str) -> str:
    """Deterministic briefing used when external LLM call is unavailable."""
    return (
        f"Geopolitical briefing for {country_code}: "
        f"{summary} "
        "Interpretation: monitor changes in tone, Goldstein score, and event mix "
        "for escalation or de-escalation signals."
    )


@dataclass
class GroqBriefingClient:
    """Small async client for Groq Chat Completions API."""

    api_key: str
    model: str = "llama-3.3-70b-versatile"

    async def generate_briefing(self, country_code: str, summary: str) -> str | None:
        prompt = (
            "Summarize the geopolitical situation in "
            f"{country_code} based on these recent events: {summary}. "
            "Be concise, factual, and around 150 words."
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a geopolitical analyst."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 320,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None


def build_forecasts_dataframe(settings: Settings) -> pd.DataFrame:
    """Compute 30-day forecasts for top 50 countries and return as dataframe."""
    hot_dir = Path(settings.hot_tier_path)
    parquet_files = list(hot_dir.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in hot-tier path: {hot_dir}")

    conn = duckdb.connect(database=":memory:")
    parquet_glob = str(hot_dir / "*.parquet")

    today = date.today()
    forecast_horizon = 30
    training_start = today - timedelta(days=90)
    training_start_int = sql_date_int(training_start)
    end_exclusive_int = sql_date_int(today + timedelta(days=1))

    top_countries = top_countries_by_volume(
        conn,
        parquet_glob,
        training_start_int,
        end_exclusive_int,
        limit=50,
    )

    forecasting_service = ForecastingService()
    rows: list[dict] = []
    generated_at = datetime.utcnow().isoformat()

    for country_code in top_countries:
        historical = fetch_conflict_daily_counts(
            conn,
            parquet_glob,
            country_code,
            training_start_int,
            end_exclusive_int,
        )
        result = forecasting_service.forecast(
            historical_counts=historical,
            horizon_days=forecast_horizon,
            country_code=country_code,
        )

        for point in result.predictions:
            rows.append(
                {
                    "country_code": country_code,
                    "date": point.date,
                    "predicted_count": point.predicted_count,
                    "lower_bound": point.lower_bound,
                    "upper_bound": point.upper_bound,
                    "model_type": result.model_type,
                    "horizon_days": forecast_horizon,
                    "generated_at": generated_at,
                }
            )

    conn.close()
    return pd.DataFrame(rows)


async def build_briefings_payload(settings: Settings) -> dict[str, dict[str, str]]:
    """Compute briefings for top 30 countries over last 7 days."""
    hot_dir = Path(settings.hot_tier_path)
    parquet_files = list(hot_dir.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in hot-tier path: {hot_dir}")

    conn = duckdb.connect(database=":memory:")
    parquet_glob = str(hot_dir / "*.parquet")

    today = date.today()
    lookback_start = today - timedelta(days=7)
    start_int = sql_date_int(lookback_start)
    end_exclusive_int = sql_date_int(today + timedelta(days=1))

    top_countries = top_countries_by_volume(
        conn,
        parquet_glob,
        start_int,
        end_exclusive_int,
        limit=30,
    )

    groq_client = None
    groq_key = getattr(settings, "groq_api_key", None)
    if isinstance(groq_key, str) and groq_key.strip():
        groq_client = GroqBriefingClient(api_key=groq_key.strip())

    payload: dict[str, dict[str, str]] = {}
    generated_at = datetime.utcnow().isoformat()

    for country_code in top_countries:
        summary = build_country_event_summary(
            conn,
            parquet_glob,
            country_code,
            start_int,
            end_exclusive_int,
        )

        briefing_text = None
        source = "fallback"
        if groq_client is not None:
            briefing_text = await groq_client.generate_briefing(country_code, summary)
            if briefing_text:
                source = "groq"

        if not briefing_text:
            briefing_text = fallback_briefing(country_code, summary)

        payload[country_code] = {
            "briefing": briefing_text,
            "generated_at": generated_at,
            "source": source,
            "summary": summary,
        }

    conn.close()
    return payload


def run_nightly_ai() -> tuple[Path, Path]:
    """Run nightly forecast and briefing precompute and write cache outputs."""
    settings = Settings()
    cache_dir = Path(settings.cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    forecasts_df = build_forecasts_dataframe(settings)
    forecasts_path = cache_dir / "forecasts.parquet"
    forecasts_df.to_parquet(forecasts_path, index=False)

    briefings = asyncio.run(build_briefings_payload(settings))
    briefings_path = cache_dir / "briefings.json"
    with briefings_path.open("w", encoding="utf-8") as handle:
        json.dump(briefings, handle, indent=2)

    print(
        f"Nightly AI success: forecasts={forecasts_path}, briefings={briefings_path}, "
        f"countries={len(briefings)}"
    )
    return forecasts_path, briefings_path


if __name__ == "__main__":
    run_nightly_ai()
