"""GDELT event repository — implements IEventRepository using BigQuery.

All SQL queries against the GDELT dataset live exclusively in this module.
No other file in the codebase should contain GDELT SQL strings.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog
from google.cloud import bigquery

from backend.domain.models.event import (
    Event,
    EventCountByDate,
    EventFilter,
    MapAggregation,
    MapEventDetail,
)
from backend.domain.ports.ports import IEventRepository
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.data_access.bigquery_client import BigQueryClient

logger = structlog.get_logger(__name__)


class GdeltRepository(IEventRepository):
    """BigQuery-backed implementation of the GDELT event repository.

    Constructs parameterised SQL queries, delegates execution to
    ``BigQueryClient``, and maps raw row dicts into domain models.
    """

    def __init__(self, bq_client: BigQueryClient, settings: Settings) -> None:
        self._bq = bq_client
        self._settings = settings
        table_name = settings.gdelt_table
        if not table_name.endswith("_partitioned"):
            table_name = f"{table_name}_partitioned"
        self._is_partitioned = table_name.endswith("_partitioned")
        self._table = f"`{settings.gdelt_dataset}.{table_name}`"

    # ------------------------------------------------------------------
    # IEventRepository implementation
    # ------------------------------------------------------------------

    def get_events(self, filters: EventFilter) -> list[Event]:
        """Retrieve events matching the given filters."""
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit

        where_clauses = self._date_where_clauses()
        params = self._build_date_params(start_date, end_date)

        if filters.country_code:
            where_clauses.append(
                "(Actor1CountryCode = @country_code "
                "OR ActionGeo_CountryCode = @country_code)"
            )
            params["country_code"] = bigquery.ScalarQueryParameter(
                "country_code", "STRING", filters.country_code.upper()
            )

        if filters.event_root_code:
            where_clauses.append("EventRootCode = @event_root_code")
            params["event_root_code"] = bigquery.ScalarQueryParameter(
                "event_root_code", "STRING", filters.event_root_code
            )

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
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            ORDER BY SQLDATE DESC
            LIMIT @limit
        """
        params["limit"] = bigquery.ScalarQueryParameter("limit", "INT64", limit)

        rows = self._bq.execute_query(sql, params)
        return [self._row_to_event(row) for row in rows]

    def get_events_by_region(
        self,
        country_code: str,
        filters: EventFilter,
    ) -> list[Event]:
        """Retrieve events for a specific country/region."""
        # Delegate to get_events with the country_code set on the filter.
        region_filter = filters.model_copy(
            update={"country_code": country_code.upper()}
        )
        return self.get_events(region_filter)

    def get_event_counts_by_date(
        self,
        country_code: str | None,
        filters: EventFilter,
    ) -> list[EventCountByDate]:
        """Get daily-aggregated event counts."""
        start_date, end_date = self._resolve_dates(filters)

        where_clauses = self._date_where_clauses()
        params = self._build_date_params(start_date, end_date)

        if country_code:
            where_clauses.append(
                "(Actor1CountryCode = @country_code "
                "OR ActionGeo_CountryCode = @country_code)"
            )
            params["country_code"] = bigquery.ScalarQueryParameter(
                "country_code", "STRING", country_code.upper()
            )

        sql = f"""
            SELECT
                SQLDATE,
                COUNT(*) AS event_count,
                AVG(GoldsteinScale) AS avg_goldstein,
                SUM(NumMentions) AS total_mentions,
                AVG(AvgTone) AS avg_tone
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            GROUP BY SQLDATE
            ORDER BY SQLDATE ASC
        """

        rows = self._bq.execute_query(sql, params)
        return [self._row_to_count(row) for row in rows]

    def get_map_aggregations(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
        grid_precision: int = 2
    ) -> list[MapAggregation]:
        """Get aggregated event counts for a geographic region."""
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit

        where_clauses = [
            *self._date_where_clauses(),
            "ActionGeo_Lat <= @bbox_n",
            "ActionGeo_Lat >= @bbox_s",
            "ActionGeo_Long <= @bbox_e",
            "ActionGeo_Long >= @bbox_w",
        ]
        params: dict[str, Any] = {
            "bbox_n": bigquery.ScalarQueryParameter("bbox_n", "FLOAT64", bbox_n),
            "bbox_s": bigquery.ScalarQueryParameter("bbox_s", "FLOAT64", bbox_s),
            "bbox_e": bigquery.ScalarQueryParameter("bbox_e", "FLOAT64", bbox_e),
            "bbox_w": bigquery.ScalarQueryParameter("bbox_w", "FLOAT64", bbox_w),
            "grid_precision": bigquery.ScalarQueryParameter("grid_precision", "INT64", grid_precision),
            "limit": bigquery.ScalarQueryParameter("limit", "INT64", limit),
        }
        params.update(self._build_date_params(start_date, end_date))

        if filters.event_root_code:
            where_clauses.append("EventRootCode = @event_root_code")
            params["event_root_code"] = bigquery.ScalarQueryParameter(
                "event_root_code", "STRING", filters.event_root_code
            )

        sql = f"""
            SELECT
                ROUND(ActionGeo_Lat, @grid_precision) AS lat,
                ROUND(ActionGeo_Long, @grid_precision) AS lon,
                COUNT(*) AS intensity
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            GROUP BY lat, lon
            LIMIT @limit
        """

        rows = self._bq.execute_query(sql, params)
        return [
            MapAggregation(
                lat=row["lat"],
                lon=row["lon"],
                intensity=row["intensity"]
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
        """Get detailed events for a geographic region."""
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit

        where_clauses = [
            *self._date_where_clauses(),
            "ActionGeo_Lat <= @bbox_n",
            "ActionGeo_Lat >= @bbox_s",
            "ActionGeo_Long <= @bbox_e",
            "ActionGeo_Long >= @bbox_w",
            "NumMentions >= @min_mentions",
        ]
        params: dict[str, Any] = {
            "bbox_n": bigquery.ScalarQueryParameter("bbox_n", "FLOAT64", bbox_n),
            "bbox_s": bigquery.ScalarQueryParameter("bbox_s", "FLOAT64", bbox_s),
            "bbox_e": bigquery.ScalarQueryParameter("bbox_e", "FLOAT64", bbox_e),
            "bbox_w": bigquery.ScalarQueryParameter("bbox_w", "FLOAT64", bbox_w),
            "min_mentions": bigquery.ScalarQueryParameter("min_mentions", "INT64", min_mentions),
            "limit": bigquery.ScalarQueryParameter("limit", "INT64", limit),
        }
        params.update(self._build_date_params(start_date, end_date))

        if filters.event_root_code:
            where_clauses.append("EventRootCode = @event_root_code")
            params["event_root_code"] = bigquery.ScalarQueryParameter(
                "event_root_code", "STRING", filters.event_root_code
            )

        # Simple query for now, joining with GKG could be added if needed for specific IDs.
        # But for map dots, we just need basic metadata.
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
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            LIMIT @limit
        """

        rows = self._bq.execute_query(sql, params)
        return [self._row_to_map_detail(row) for row in rows]

    def get_event_by_id(self, event_id: int) -> Event | None:
        """Retrieve a single event by its unique GLOBALEVENTID."""
        # Keep this lookup partition-pruned by constraining to the configured default window.
        end_date = date.today()
        start_date = end_date - timedelta(days=self._settings.default_lookback_days)

        where_clauses = self._date_where_clauses()
        where_clauses.append("GLOBALEVENTID = @event_id")

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
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            LIMIT 1
        """
        params: dict[str, Any] = {
            "event_id": bigquery.ScalarQueryParameter("event_id", "INT64", event_id)
        }
        params.update(self._build_date_params(start_date, end_date))

        rows = self._bq.execute_query(sql, params)
        if not rows:
            return None
        return self._row_to_event(rows[0])

    @staticmethod
    def _row_to_map_detail(row: dict[str, Any]) -> MapEventDetail:
        """Map a BigQuery row to a MapEventDetail model."""
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_dates(self, filters: EventFilter) -> tuple[date, date]:
        """Fill in default start/end dates when not supplied by the caller."""
        end = filters.end_date or date.today()
        start = filters.start_date or (
            end - timedelta(days=self._settings.default_lookback_days)
        )
        return start, end

    def _date_where_clauses(self) -> list[str]:
        clauses = ["SQLDATE >= @start_date", "SQLDATE < @end_date_exclusive"]
        if self._is_partitioned:
            clauses.extend(
                [
                    "_PARTITIONDATE >= @start_partition_date",
                    "_PARTITIONDATE < @end_partition_date_exclusive",
                ]
            )
        return clauses

    def _build_date_params(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[str, bigquery.ScalarQueryParameter]:
        params = self._build_sql_date_params(start_date, end_date)
        if self._is_partitioned:
            end_date_exclusive = end_date + timedelta(days=1)
            params["start_partition_date"] = bigquery.ScalarQueryParameter(
                "start_partition_date", "DATE", start_date.isoformat()
            )
            params["end_partition_date_exclusive"] = bigquery.ScalarQueryParameter(
                "end_partition_date_exclusive", "DATE", end_date_exclusive.isoformat()
            )
        return params

    @staticmethod
    def _build_sql_date_params(start_date: date, end_date: date) -> dict[str, bigquery.ScalarQueryParameter]:
        """Build SQLDATE partition parameters with an exclusive upper bound."""
        end_date_exclusive = end_date + timedelta(days=1)
        return {
            "start_date": bigquery.ScalarQueryParameter(
                "start_date", "INT64", int(start_date.strftime("%Y%m%d"))
            ),
            "end_date_exclusive": bigquery.ScalarQueryParameter(
                "end_date_exclusive", "INT64", int(end_date_exclusive.strftime("%Y%m%d"))
            ),
        }

    @staticmethod
    def _row_to_event(row: dict[str, Any]) -> Event:
        """Map a BigQuery row dict to a domain Event model."""
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
        """Map a BigQuery aggregation row to an EventCountByDate model."""
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
