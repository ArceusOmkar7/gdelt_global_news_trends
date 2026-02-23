"""GDELT event repository — implements IEventRepository using BigQuery.

All SQL queries against the GDELT dataset live exclusively in this module.
No other file in the codebase should contain GDELT SQL strings.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog
from google.cloud import bigquery

from backend.domain.models.event import Event, EventCountByDate, EventFilter
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
        self._table = f"`{settings.gdelt_dataset}.{settings.gdelt_table}`"

    # ------------------------------------------------------------------
    # IEventRepository implementation
    # ------------------------------------------------------------------

    def get_events(self, filters: EventFilter) -> list[Event]:
        """Retrieve events matching the given filters."""
        start_date, end_date = self._resolve_dates(filters)
        limit = filters.limit or self._settings.default_query_limit

        where_clauses = ["SQLDATE >= @start_date", "SQLDATE <= @end_date"]
        params: dict[str, Any] = {
            "start_date": bigquery.ScalarQueryParameter(
                "start_date", "INT64", int(start_date.strftime("%Y%m%d"))
            ),
            "end_date": bigquery.ScalarQueryParameter(
                "end_date", "INT64", int(end_date.strftime("%Y%m%d"))
            ),
        }

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
                NumArticles,
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

        where_clauses = ["SQLDATE >= @start_date", "SQLDATE <= @end_date"]
        params: dict[str, Any] = {
            "start_date": bigquery.ScalarQueryParameter(
                "start_date", "INT64", int(start_date.strftime("%Y%m%d"))
            ),
            "end_date": bigquery.ScalarQueryParameter(
                "end_date", "INT64", int(end_date.strftime("%Y%m%d"))
            ),
        }

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
                SUM(NumArticles) AS total_articles,
                AVG(AvgTone) AS avg_tone
            FROM {self._table}
            WHERE {' AND '.join(where_clauses)}
            GROUP BY SQLDATE
            ORDER BY SQLDATE ASC
        """

        rows = self._bq.execute_query(sql, params)
        return [self._row_to_count(row) for row in rows]

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
            num_articles=row.get("NumArticles", 0),
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
            total_articles=row.get("total_articles", 0),
            avg_tone=row.get("avg_tone"),
        )
