"""DuckDB hot-tier repository backed by local Parquet files.

This repository is intended for recent-data queries served from the local
hot tier. It implements the same IEventRepository contract used by the
BigQuery repository.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
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


class DuckDbRepositoryError(Exception):
    """Raised when hot-tier DuckDB repository preconditions are not met."""


class DuckDbRepository(IEventRepository):
    """DuckDB-backed implementation of the event repository for hot-tier data."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn = duckdb.connect(database=":memory:")
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

        where_clauses = [
            "SQLDATE >= ?",
            "SQLDATE < ?",
            "ActionGeo_Lat IS NOT NULL",
            "ActionGeo_Long IS NOT NULL",
            "ActionGeo_Lat <= ?",
            "ActionGeo_Lat >= ?",
            "ActionGeo_Long <= ?",
            "ActionGeo_Long >= ?",
        ]
        params: list[Any] = [
            start_int,
            end_exclusive_int,
            bbox_n,
            bbox_s,
            bbox_e,
            bbox_w,
        ]

        if filters.event_root_code:
            where_clauses.append("EventRootCode = ?")
            params.append(filters.event_root_code)

        sql = f"""
            SELECT
                ROUND(ActionGeo_Lat, ?) AS lat,
                ROUND(ActionGeo_Long, ?) AS lon,
                COUNT(*) AS intensity
            FROM read_parquet('{self._parquet_glob}')
            WHERE {' AND '.join(where_clauses)}
            GROUP BY lat, lon
            LIMIT ?
        """
        # Parameter order must match SQL placeholder order.
        params = [grid_precision, grid_precision, *params, limit]

        rows = self._query(sql, params)
        return [
            MapAggregation(
                lat=row["lat"],
                lon=row["lon"],
                intensity=row["intensity"],
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
    ) -> list[MapEventDetail]:
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit
        start_int, end_exclusive_int = self._sql_date_bounds(start_date, end_date)

        where_clauses = [
            "SQLDATE >= ?",
            "SQLDATE < ?",
            "ActionGeo_Lat IS NOT NULL",
            "ActionGeo_Long IS NOT NULL",
            "ActionGeo_Lat <= ?",
            "ActionGeo_Lat >= ?",
            "ActionGeo_Long <= ?",
            "ActionGeo_Long >= ?",
        ]
        params: list[Any] = [
            start_int,
            end_exclusive_int,
            bbox_n,
            bbox_s,
            bbox_e,
            bbox_w,
        ]

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
                GoldsteinScale,
                NumMentions,
                NumSources,
                AvgTone,
                SOURCEURL,
                Actor1Type1Code AS Actor1Type,
                Actor2Type1Code AS Actor2Type
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        """Execute a DuckDB query and return rows as dictionaries."""
        logger.debug("duckdb_query", sql_preview=sql[:200], params_count=len(params))
        result = self._conn.execute(sql, params)
        columns = [col[0] for col in (result.description or [])]
        values = result.fetchall()
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
            goldstein_scale=row.get("GoldsteinScale"),
            num_mentions=row.get("NumMentions", 0),
            num_sources=row.get("NumSources", 0),
            avg_tone=row.get("AvgTone"),
            source_url=row.get("SOURCEURL"),
            actor1_type=row.get("Actor1Type"),
            actor2_type=row.get("Actor2Type"),
        )
