"""DuckDB hot-tier repository backed by local Parquet files.

This repository is intended for recent-data queries served from the local
hot tier. It implements the same IEventRepository contract used by the
BigQuery repository.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
import threading
from typing import Any

import duckdb
import structlog

from backend.domain.models.event import (
    Event,
    EventCountByDate,
    EventFilter,
    MapAggregation,
    MapEventDetail,
)
from backend.domain.ports.ports import IEventRepository
from backend.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


def compute_risk_score(conflict_ratio, avg_goldstein, avg_tone) -> int:
    # conflict_ratio: 0.0–1.0, higher = more conflict
    # avg_goldstein: -10 to +10, more negative = more conflict
    # avg_tone: typically -30 to +30, more negative = more hostile
    conflict_ratio = float(conflict_ratio or 0.0)
    avg_goldstein = float(avg_goldstein) if avg_goldstein is not None else 0.0
    avg_tone = float(avg_tone) if avg_tone is not None else 0.0

    goldstein_score = max(0, min(100, ((-avg_goldstein + 10) / 20) * 100))
    tone_score = max(0, min(100, ((-avg_tone + 30) / 60) * 100))
    conflict_score = conflict_ratio * 100
    return round(conflict_score * 0.4 + goldstein_score * 0.35 + tone_score * 0.25)


class DuckDbRepositoryError(Exception):
    """Raised when hot-tier DuckDB repository preconditions are not met."""


class DuckDbRepository(IEventRepository):
    """DuckDB-backed implementation of the event repository for hot-tier data."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn = duckdb.connect(database=":memory:")
        self._conn_lock = threading.Lock()
        hot_tier_dir = Path(settings.hot_tier_path)
        self._parquet_glob = str(hot_tier_dir / "*.parquet")

        if not hot_tier_dir.exists() or not hot_tier_dir.is_dir():
            raise DuckDbRepositoryError(
                f"Hot-tier path does not exist or is not a directory: {hot_tier_dir}"
            )

        if not any(hot_tier_dir.glob("*.parquet")):
            raise DuckDbRepositoryError(
                f"No parquet files found in hot-tier path: {hot_tier_dir}"
            )

    def get_ingestion_stats(self) -> dict[str, Any]:
        """Returns row count, coverage days, and last modified time for the hot tier."""
        hot_tier_dir = Path(self._settings.hot_tier_path)
        if not hot_tier_dir.exists() or not any(hot_tier_dir.glob("*.parquet")):
            return {"total_rows": 0, "coverage_days": 0, "last_updated_at": None}
 
        try:
            sql = f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COUNT(DISTINCT SQLDATE) AS days
                FROM read_parquet('{self._parquet_glob}')
            """
            rows = self._query(sql, [])
            total_rows = int(rows[0]["cnt"]) if rows else 0
            coverage_days = int(rows[0]["days"]) if rows else 0
 
            files = list(hot_tier_dir.glob("*.parquet"))
            if not files:
                return {
                    "total_rows": total_rows, 
                    "coverage_days": coverage_days,
                    "last_updated_at": None
                }
 
            latest_mtime = max(f.stat().st_mtime for f in files)
            last_updated = datetime.fromtimestamp(latest_mtime).isoformat()
 
            return {
                "total_rows": total_rows, 
                "coverage_days": coverage_days,
                "last_updated_at": last_updated
            }
        except Exception as e:
            logger.error("failed_to_get_ingestion_stats", error=str(e))
            return {"total_rows": 0, "coverage_days": 0, "last_updated_at": None}
 

    # ------------------------------------------------------------------
    # IEventRepository implementation
    # ------------------------------------------------------------------

    def get_events(self, filters: EventFilter) -> list[Event]:
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        where_clauses = ["SQLDATE >= ?", "SQLDATE < ?"]
        params: list[Any] = [start_int, end_exclusive_int]

        if filters.country_code:
            where_clauses.append(
                "(Actor1CountryCode = ? OR ActionGeo_CountryCode = ?)"
            )
            cc = filters.country_code.upper()
            params.extend([cc, cc])

        if filters.event_root_code:
            where_clauses.append("EventRootCode = ?")
            params.append(filters.event_root_code)

        sql = f"""
            SELECT
                GLOBALEVENTID,
                SQLDATE,
                Actor1CountryCode,
                Actor2CountryCode,
                EventRootCode,
                EventCode,
                GoldsteinScale,
                NumMentions,
                NumSources,
                AvgTone,
                themes,
                persons,
                organizations,
                mentions_count,
                avg_confidence,
                ActionGeo_CountryCode,
                ActionGeo_Lat,
                ActionGeo_Long,
                SOURCEURL
            FROM read_parquet('{self._parquet_glob}')
            WHERE {' AND '.join(where_clauses)}
            ORDER BY SQLDATE DESC
            LIMIT ?
        """
        params.append(limit)

        rows = self._query(sql, params)
        return [self._row_to_event(row) for row in rows]

    def get_events_by_region(
        self,
        country_code: str,
        filters: EventFilter,
    ) -> list[Event]:
        region_filter = filters.model_copy(update={"country_code": country_code.upper()})
        return self.get_events(region_filter)

    def get_event_counts_by_date(
        self,
        country_code: str | None,
        filters: EventFilter,
    ) -> list[EventCountByDate]:
        start_date, end_date = self._resolve_dates(filters)
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        where_clauses = ["SQLDATE >= ?", "SQLDATE < ?"]
        params: list[Any] = [start_int, end_exclusive_int]

        if country_code:
            where_clauses.append(
                "(Actor1CountryCode = ? OR ActionGeo_CountryCode = ?)"
            )
            cc = country_code.upper()
            params.extend([cc, cc])

        sql = f"""
            SELECT
                SQLDATE,
                COUNT(*) AS event_count,
                AVG(GoldsteinScale) AS avg_goldstein,
                SUM(NumMentions) AS total_mentions,
                AVG(AvgTone) AS avg_tone
            FROM read_parquet('{self._parquet_glob}')
            WHERE {' AND '.join(where_clauses)}
            GROUP BY SQLDATE
            ORDER BY SQLDATE ASC
        """

        rows = self._query(sql, params)
        return [self._row_to_count(row) for row in rows]

    def get_map_aggregations(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
        grid_precision: int = 2,
    ) -> list[MapAggregation]:
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        # Normalize longitudes to [-180, 180] for DuckDB
        # If view is wider than 360 degrees, skip longitude filtering
        if abs(bbox_e - bbox_w) >= 360:
            norm_w = -180.0
            norm_e = 180.0
            is_full_world = True
        else:
            norm_w = ((bbox_w + 180) % 360) - 180
            norm_e = ((bbox_e + 180) % 360) - 180
            is_full_world = False

        where_clauses = [
            "SQLDATE >= ?",
            "SQLDATE < ?",
            "ActionGeo_Lat IS NOT NULL",
            "ActionGeo_Long IS NOT NULL",
            "ActionGeo_Lat <= ?",
            "ActionGeo_Lat >= ?",
        ]
        params: list[Any] = [
            start_int,
            end_exclusive_int,
            bbox_n,
            bbox_s,
        ]

        if not is_full_world:
            if norm_w <= norm_e:
                where_clauses.append("ActionGeo_Long <= ?")
                where_clauses.append("ActionGeo_Long >= ?")
                params.extend([norm_e, norm_w])
            else:
                # Crosses International Date Line
                where_clauses.append("(ActionGeo_Long <= ? OR ActionGeo_Long >= ?)")
                params.extend([norm_e, norm_w])

        if filters.event_root_code:
            where_clauses.append("EventRootCode = ?")
            params.append(filters.event_root_code)

        sql = f"""
            SELECT
                ROUND(ActionGeo_Lat, ?) AS lat,
                ROUND(ActionGeo_Long, ?) AS lon,
                MODE(ActionGeo_CountryCode) AS country_code,
                COUNT(*) AS intensity
            FROM read_parquet('{self._parquet_glob}')
            WHERE {' AND '.join(where_clauses)}
            GROUP BY lat, lon
            LIMIT ?
        """
        all_params = [grid_precision, grid_precision, *params, limit]

        rows = self._query(sql, all_params)
        return [
            MapAggregation(
                lat=row["lat"],
                lon=row["lon"],
                intensity=row["intensity"],
                country_code=row.get("country_code"),
            )
            for row in rows
        ]

    def get_event_details(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
        min_mentions: int = 1,
    ) -> list[MapEventDetail]:
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        # Normalize longitudes to [-180, 180] for DuckDB
        # If view is wider than 360 degrees, skip longitude filtering
        if abs(bbox_e - bbox_w) >= 360:
            norm_w = -180.0
            norm_e = 180.0
            is_full_world = True
        else:
            norm_w = ((bbox_w + 180) % 360) - 180
            norm_e = ((bbox_e + 180) % 360) - 180
            is_full_world = False

        where_clauses = [
            "SQLDATE >= ?",
            "SQLDATE < ?",
            "ActionGeo_Lat IS NOT NULL",
            "ActionGeo_Long IS NOT NULL",
            "ActionGeo_Lat <= ?",
            "ActionGeo_Lat >= ?",
            "NumMentions >= ?",
        ]
        params: list[Any] = [
            start_int,
            end_exclusive_int,
            bbox_n,
            bbox_s,
            min_mentions,
        ]

        if not is_full_world:
            if norm_w <= norm_e:
                where_clauses.append("ActionGeo_Long <= ?")
                where_clauses.append("ActionGeo_Long >= ?")
                params.extend([norm_e, norm_w])
            else:
                # Crosses International Date Line
                where_clauses.append("(ActionGeo_Long <= ? OR ActionGeo_Long >= ?)")
                params.extend([norm_e, norm_w])

        if filters.event_root_code:
            where_clauses.append("EventRootCode = ?")
            params.append(filters.event_root_code)

        sql = f"""
            SELECT
                GLOBALEVENTID,
                SQLDATE,
                ActionGeo_Lat AS lat,
                ActionGeo_Long AS lon,
                Actor1CountryCode,
                Actor2CountryCode,
                EventRootCode,
                QuadClass,
                Actor1Type1Code AS actor1_type_code,
                Actor2Type1Code AS actor2_type_code,
                EventCode,
                Actor1Geo_CountryCode,
                Actor2Geo_CountryCode,
                GoldsteinScale,
                NumMentions,
                NumSources,
                AvgTone,
                SOURCEURL,
                Actor1Type1Code AS Actor1Type,
                Actor2Type1Code AS Actor2Type,
                themes,
                persons,
                organizations
            FROM read_parquet('{self._parquet_glob}')
            WHERE {' AND '.join(where_clauses)}
            LIMIT ?
        """
        params.append(limit)

        rows = self._query(sql, params)
        return [self._row_to_map_detail(row) for row in rows]

    def get_event_by_id(self, event_id: int) -> Event | None:
        # Keep event lookup partition-pruned to the default lookback window.
        end_date = date.today()
        start_date = end_date - timedelta(days=self._settings.default_lookback_days)
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        sql = f"""
            SELECT
                GLOBALEVENTID,
                SQLDATE,
                Actor1CountryCode,
                Actor2CountryCode,
                EventRootCode,
                EventCode,
                GoldsteinScale,
                NumMentions,
                NumSources,
                AvgTone,
                themes,
                persons,
                organizations,
                mentions_count,
                avg_confidence,
                ActionGeo_CountryCode,
                ActionGeo_Lat,
                ActionGeo_Long,
                SOURCEURL
            FROM read_parquet('{self._parquet_glob}')
            WHERE SQLDATE >= ?
              AND SQLDATE < ?
              AND GLOBALEVENTID = ?
            LIMIT 1
        """

        rows = self._query(sql, [start_int, end_exclusive_int, event_id])
        if not rows:
            return None
        return self._row_to_event(rows[0])

    def get_risk_score(
        self,
        country_code: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        sql = f"""
            SELECT
                COUNT(*) AS total_events,
                CASE
                    WHEN COUNT(*) = 0 THEN 0.0
                    ELSE SUM(CASE WHEN QuadClass IN (3, 4) THEN 1 ELSE 0 END) * 1.0 / COUNT(*)
                END AS conflict_ratio,
                AVG(GoldsteinScale) AS avg_goldstein,
                AVG(AvgTone) AS avg_tone,
                COALESCE(SUM(NumMentions), 0) AS total_mentions
            FROM read_parquet('{self._parquet_glob}')
            WHERE ActionGeo_CountryCode = ?
              AND SQLDATE >= ?
              AND SQLDATE < ?
        """

        rows = self._query(sql, [country_code.upper(), start_int, end_exclusive_int])
        if not rows:
            return {
                "total_events": 0,
                "conflict_ratio": 0.0,
                "avg_goldstein": None,
                "avg_tone": None,
                "total_mentions": 0,
            }

        row = rows[0]
        return {
            "total_events": int(row.get("total_events") or 0),
            "conflict_ratio": float(row.get("conflict_ratio") or 0.0),
            "avg_goldstein": row.get("avg_goldstein"),
            "avg_tone": row.get("avg_tone"),
            "total_mentions": int(row.get("total_mentions") or 0),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        """Execute a DuckDB query and return rows as dictionaries."""
        logger.debug("duckdb_query", sql_preview=sql[:200], params_count=len(params))
        # # DuckDB connections are not safe for concurrent execute/fetch cycles.
        # # FastAPI can process sync route handlers in parallel threads.
        # with self._conn_lock:
        #     result = self._conn.execute(sql, params)
        #     columns = [col[0] for col in (result.description or [])]
        #     values = result.fetchall()
        # return [dict(zip(columns, row)) for row in values]
        conn = duckdb.connect(database=":memory:", read_only=False)
        try:
            result = conn.execute(sql, params)
            columns = [col[0] for col in (result.description or [])]
            values = result.fetchall()
        finally:
            conn.close()
        return [dict(zip(columns, row)) for row in values]

    def _resolve_dates(self, filters: EventFilter) -> tuple[date, date]:
        end = filters.end_date or date.today()
        start = filters.start_date or (end - timedelta(days=self._settings.default_lookback_days))
        return start, end

    @staticmethod
    def _sql_date_bounds(start_date: date, end_date: date) -> tuple[int, int]:
        end_date_exclusive = end_date + timedelta(days=1)
        return int(start_date.strftime("%Y%m%d")), int(end_date_exclusive.strftime("%Y%m%d"))

    @staticmethod
    def _row_to_event(row: dict[str, Any]) -> Event:
        sql_date_raw = row.get("SQLDATE")
        if isinstance(sql_date_raw, int):
            sql_date_str = str(sql_date_raw)
            parsed_date = date(
                int(sql_date_str[:4]),
                int(sql_date_str[4:6]),
                int(sql_date_str[6:8]),
            )
        else:
            parsed_date = sql_date_raw

        return Event(
            global_event_id=row["GLOBALEVENTID"],
            sql_date=parsed_date,
            actor1_country_code=row.get("Actor1CountryCode"),
            actor2_country_code=row.get("Actor2CountryCode"),
            event_root_code=row.get("EventRootCode"),
            event_code=row.get("EventCode"),
            goldstein_scale=row.get("GoldsteinScale"),
            num_mentions=row.get("NumMentions", 0),
            num_sources=row.get("NumSources", 0),
            avg_tone=row.get("AvgTone"),
            themes=row.get("themes", []),
            persons=row.get("persons", []),
            organizations=row.get("organizations", []),
            mentions_count=int(row.get("mentions_count") or 0),
            avg_confidence=row.get("avg_confidence"),
            action_geo_country_code=row.get("ActionGeo_CountryCode"),
            action_geo_lat=row.get("ActionGeo_Lat"),
            action_geo_long=row.get("ActionGeo_Long"),
            source_url=row.get("SOURCEURL"),
        )

    @staticmethod
    def _row_to_count(row: dict[str, Any]) -> EventCountByDate:
        sql_date_raw = row.get("SQLDATE")
        if isinstance(sql_date_raw, int):
            sql_date_str = str(sql_date_raw)
            parsed_date = date(
                int(sql_date_str[:4]),
                int(sql_date_str[4:6]),
                int(sql_date_str[6:8]),
            )
        else:
            parsed_date = sql_date_raw

        return EventCountByDate(
            date=parsed_date,
            count=row.get("event_count", 0),
            avg_goldstein_scale=row.get("avg_goldstein"),
            total_mentions=row.get("total_mentions", 0),
            avg_tone=row.get("avg_tone"),
        )

    @staticmethod
    def _row_to_map_detail(row: dict[str, Any]) -> MapEventDetail:
        sql_date_raw = row.get("SQLDATE")
        if isinstance(sql_date_raw, int):
            sql_date_str = str(sql_date_raw)
            parsed_date = date(
                int(sql_date_str[:4]),
                int(sql_date_str[4:6]),
                int(sql_date_str[6:8]),
            )
        else:
            parsed_date = sql_date_raw

        return MapEventDetail(
            global_event_id=row["GLOBALEVENTID"],
            sql_date=parsed_date,
            lat=row["lat"],
            lon=row["lon"],
            actor1_country_code=row.get("Actor1CountryCode"),
            actor2_country_code=row.get("Actor2CountryCode"),
            event_root_code=row.get("EventRootCode"),
            quad_class=row.get("QuadClass"),
            actor1_type_code=row.get("actor1_type_code"),
            actor2_type_code=row.get("actor2_type_code"),
            event_code=row.get("EventCode"),
            actor1_geo_country_code=row.get("Actor1Geo_CountryCode"),
            actor2_geo_country_code=row.get("Actor2Geo_CountryCode"),
            goldstein_scale=row.get("GoldsteinScale"),
            num_mentions=row.get("NumMentions", 0),
            num_sources=row.get("NumSources", 0),
            avg_tone=row.get("AvgTone"),
            source_url=row.get("SOURCEURL"),
            actor1_type=row.get("Actor1Type"),
            actor2_type=row.get("Actor2Type"),
            themes=row.get("themes", []),
            persons=row.get("persons", []),
            organizations=row.get("organizations", []),
        )

    # ------------------------------------------------------------------
    # 15.1 — Global Pulse
    # ------------------------------------------------------------------
 
    def get_global_pulse(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Return global aggregate stats for the stats ticker.
 
        Two queries are run:
          1. Single-pass aggregation for totals, most-active country, avg tone,
             conflict ratio.
          2. Grouped per-country to find the most hostile country (lowest avg tone).
 
        Both use fresh in-process DuckDB connections (no shared lock).
        """
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)
 
        # Query 1 — global aggregates + most-active country
        sql_global = f"""
            SELECT
                COUNT(*)                                                              AS total_events,
                MODE(ActionGeo_CountryCode)                                           AS most_active_country,
                AVG(AvgTone)                                                          AS avg_global_tone,
                SUM(CASE WHEN QuadClass IN (3, 4) THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS conflict_ratio
            FROM read_parquet('{self._parquet_glob}')
            WHERE SQLDATE >= ? AND SQLDATE < ?
              AND ActionGeo_CountryCode IS NOT NULL
              AND ActionGeo_CountryCode != ''
        """
        global_rows = self._query(sql_global, [start_int, end_exclusive_int])
        g = global_rows[0] if global_rows else {}
 
        # Query 2 — most-active country event count (for most_active_count field)
        most_active_cc = g.get("most_active_country")
        most_active_count = 0
        if most_active_cc:
            sql_count = f"""
                SELECT COUNT(*) AS cnt
                FROM read_parquet('{self._parquet_glob}')
                WHERE SQLDATE >= ? AND SQLDATE < ?
                  AND ActionGeo_CountryCode = ?
            """
            count_rows = self._query(sql_count, [start_int, end_exclusive_int, most_active_cc])
            most_active_count = int(count_rows[0]["cnt"]) if count_rows else 0
 
        # Query 3 — most hostile country (lowest avg AvgTone, min 10 events for stability)
        sql_hostile = f"""
            SELECT ActionGeo_CountryCode AS country_code
            FROM read_parquet('{self._parquet_glob}')
            WHERE SQLDATE >= ? AND SQLDATE < ?
              AND ActionGeo_CountryCode IS NOT NULL
              AND ActionGeo_CountryCode != ''
              AND AvgTone IS NOT NULL
            GROUP BY ActionGeo_CountryCode
            HAVING COUNT(*) >= 10
            ORDER BY AVG(AvgTone) ASC
            LIMIT 1
        """
        hostile_rows = self._query(sql_hostile, [start_int, end_exclusive_int])
        most_hostile_cc = hostile_rows[0]["country_code"] if hostile_rows else None
 
        avg_tone = g.get("avg_global_tone")
        conflict_ratio = float(g.get("conflict_ratio") or 0.0)
 
        return {
            "total_events_today": int(g.get("total_events") or 0),
            "most_active_country": most_active_cc,
            "most_active_count": most_active_count,
            "most_hostile_country": most_hostile_cc,
            "avg_global_tone": float(avg_tone) if avg_tone is not None else None,
            "global_conflict_ratio": conflict_ratio,
        }
 
    # ------------------------------------------------------------------
    # 15.2 — Top Threat Countries
    # ------------------------------------------------------------------
 
    def get_top_threat_countries(
        self,
        start_date: date,
        end_date: date,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-N countries ranked by computed risk score.
 
        Fetches the top 50 countries by raw event volume, computes the risk
        score for each in Python using compute_risk_score(), sorts descending,
        and returns the top `limit` entries.
        """
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)
 
        sql = f"""
            SELECT
                ActionGeo_CountryCode                                                     AS country_code,
                COUNT(*)                                                                  AS total_events,
                SUM(CASE WHEN QuadClass IN (3, 4) THEN 1 ELSE 0 END) * 1.0 / COUNT(*)   AS conflict_ratio,
                AVG(GoldsteinScale)                                                       AS avg_goldstein,
                AVG(AvgTone)                                                              AS avg_tone
            FROM read_parquet('{self._parquet_glob}')
            WHERE SQLDATE >= ? AND SQLDATE < ?
              AND ActionGeo_CountryCode IS NOT NULL
              AND ActionGeo_CountryCode != ''
            GROUP BY ActionGeo_CountryCode
            ORDER BY total_events DESC
            LIMIT 50
        """
        rows = self._query(sql, [start_int, end_exclusive_int])
 
        scored: list[dict[str, Any]] = []
        for row in rows:
            cr = float(row.get("conflict_ratio") or 0.0)
            gs = row.get("avg_goldstein")
            at = row.get("avg_tone")
            score = compute_risk_score(cr, gs, at)
            scored.append({
                "country_code": row["country_code"],
                "score": score,
                "conflict_ratio": cr,
                "total_events": int(row.get("total_events") or 0),
            })
 
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
 
    # ------------------------------------------------------------------
    # Week-over-week Deltas
    # ------------------------------------------------------------------

    def get_analytics_deltas(self) -> dict[str, Any]:
        """Calculate WoW deltas for the top 20 countries by event volume."""
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        fourteen_days_ago = today - timedelta(days=14)

        start_7d, end_7d = self._sql_date_bounds(seven_days_ago, today)
        start_prior, end_prior = self._sql_date_bounds(fourteen_days_ago, seven_days_ago - timedelta(days=1))

        # 1. Identify top 20 countries in last 14 days
        sql_top_20 = f"""
            SELECT ActionGeo_CountryCode, COUNT(*) as cnt
            FROM read_parquet('{self._parquet_glob}')
            WHERE SQLDATE >= ? AND SQLDATE <= ?
              AND ActionGeo_CountryCode IS NOT NULL
              AND ActionGeo_CountryCode != ''
            GROUP BY ActionGeo_CountryCode
            ORDER BY cnt DESC
            LIMIT 20
        """
        top_20_rows = self._query(sql_top_20, [int(fourteen_days_ago.strftime("%Y%m%d")), int(today.strftime("%Y%m%d"))])
        top_20_ccs = [row["ActionGeo_CountryCode"] for row in top_20_rows]

        if not top_20_ccs:
            return {}

        # 2. Get stats for both periods
        def get_stats(start_int: int, end_int: int):
            sql_stats = f"""
                SELECT
                    ActionGeo_CountryCode,
                    COUNT(*) AS total_events,
                    SUM(CASE WHEN QuadClass IN (3, 4) THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS conflict_ratio,
                    AVG(GoldsteinScale) AS avg_goldstein,
                    AVG(AvgTone) AS avg_tone
                FROM read_parquet('{self._parquet_glob}')
                WHERE SQLDATE >= ? AND SQLDATE < ?
                  AND ActionGeo_CountryCode IN ({','.join(['?' for _ in top_20_ccs])})
                GROUP BY ActionGeo_CountryCode
            """
            return self._query(sql_stats, [start_int, end_int, *top_20_ccs])

        stats_7d = {row["ActionGeo_CountryCode"]: row for row in get_stats(start_7d, end_7d)}
        stats_prior = {row["ActionGeo_CountryCode"]: row for row in get_stats(start_prior, end_prior)}

        deltas = {}
        for cc in top_20_ccs:
            curr = stats_7d.get(cc, {"total_events": 0, "conflict_ratio": 0.0, "avg_goldstein": 0.0, "avg_tone": 0.0})
            prev = stats_prior.get(cc, {"total_events": 0, "conflict_ratio": 0.0, "avg_goldstein": 0.0, "avg_tone": 0.0})

            # Event delta %
            e_curr = curr["total_events"]
            e_prev = prev["total_events"]
            event_delta_pct = ((e_curr - e_prev) / max(1, e_prev)) * 100

            # Conflict delta
            c_curr = float(curr["conflict_ratio"] or 0.0)
            c_prev = float(prev["conflict_ratio"] or 0.0)
            conflict_delta = (c_curr - c_prev) * 100

            # Tone delta
            t_curr = float(curr["avg_tone"] or 0.0)
            t_prev = float(prev["avg_tone"] or 0.0)
            tone_delta = t_curr - t_prev

            # Score delta
            s_curr = compute_risk_score(c_curr, curr["avg_goldstein"], t_curr)
            s_prev = compute_risk_score(c_prev, prev["avg_goldstein"], t_prev)
            score_delta = s_curr - s_prev

            deltas[cc] = {
                "event_delta_pct": round(event_delta_pct, 1),
                "conflict_delta": round(conflict_delta, 1),
                "tone_delta": round(tone_delta, 1),
                "score_delta": int(score_delta),
            }

        return deltas
