"""Hybrid event repository that routes between hot and cold data tiers.

Routing rules:
- Hot-only window (within cutoff): DuckDB hot tier
- Cold-only window (older than cutoff): BigQuery cold tier with policy checks
- Spanning window: split request across both tiers and merge in-memory
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, TypeVar

import pandas as pd
import structlog

from backend.api.request_context import get_request_user_id
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

T = TypeVar("T")


class ColdTierPolicyError(Exception):
    """Raised when a cold-tier policy guardrail blocks a query."""


class RoutedRepository(IEventRepository):
    """Repository adapter that enforces hot/cold routing and cold-tier policy."""

    def __init__(
        self,
        hot_repository: IEventRepository,
        cold_repository: IEventRepository,
        settings: Settings,
    ) -> None:
        self._hot = hot_repository
        self._cold = cold_repository
        self._settings = settings
        self._cache_dir = Path(settings.cache_path) / "cold_queries"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._counter_file = self._cache_dir / "cold_query_counts.json"
        self._counter_lock = threading.Lock()
        self._cold_counts = self._load_cold_counts()

    # ------------------------------------------------------------------
    # IEventRepository implementation
    # ------------------------------------------------------------------

    def get_events(self, filters: EventFilter) -> list[Event]:
        start_date, end_date = self._resolve_dates(filters)
        route = self._route_for_window(start_date, end_date)

        if route == "hot":
            return self._hot.get_events(filters)

        if route == "cold":
            return self._execute_cold_with_cache(
                method="events",
                start_date=start_date,
                end_date=end_date,
                country_code=filters.country_code,
                extra={"event_root_code": filters.event_root_code, "limit": filters.limit},
                fetch=lambda: self._cold.get_events(filters),
                parse=lambda payload: Event.model_validate(payload),
            )

        cold_filters = filters.model_copy(
            update={
                "start_date": start_date,
                "end_date": self._cutoff_date() - timedelta(days=1),
            }
        )
        hot_filters = filters.model_copy(
            update={
                "start_date": self._cutoff_date(),
                "end_date": end_date,
            }
        )

        cold_rows = self._execute_cold_with_cache(
            method="events",
            start_date=cold_filters.start_date,
            end_date=cold_filters.end_date,
            country_code=filters.country_code,
            extra={"event_root_code": filters.event_root_code, "limit": filters.limit, "span": True},
            fetch=lambda: self._cold.get_events(cold_filters),
            parse=lambda payload: Event.model_validate(payload),
        )
        hot_rows = self._hot.get_events(hot_filters)

        merged = hot_rows + cold_rows
        merged.sort(key=lambda e: (e.sql_date, e.global_event_id), reverse=True)
        limit = filters.limit or self._settings.default_query_limit
        return merged[:limit]

    def get_events_by_region(self, country_code: str, filters: EventFilter) -> list[Event]:
        return self.get_events(filters.model_copy(update={"country_code": country_code.upper()}))

    def get_event_counts_by_date(
        self,
        country_code: str | None,
        filters: EventFilter,
    ) -> list[EventCountByDate]:
        start_date, end_date = self._resolve_dates(filters)
        route = self._route_for_window(start_date, end_date)

        if route == "hot":
            return self._hot.get_event_counts_by_date(country_code, filters)

        if route == "cold":
            return self._execute_cold_with_cache(
                method="daily_counts",
                start_date=start_date,
                end_date=end_date,
                country_code=country_code,
                extra={},
                fetch=lambda: self._cold.get_event_counts_by_date(country_code, filters),
                parse=lambda payload: EventCountByDate.model_validate(payload),
            )

        cutoff = self._cutoff_date()
        cold_filters = filters.model_copy(update={"start_date": start_date, "end_date": cutoff - timedelta(days=1)})
        hot_filters = filters.model_copy(update={"start_date": cutoff, "end_date": end_date})

        cold_counts = self._execute_cold_with_cache(
            method="daily_counts",
            start_date=cold_filters.start_date,
            end_date=cold_filters.end_date,
            country_code=country_code,
            extra={"span": True},
            fetch=lambda: self._cold.get_event_counts_by_date(country_code, cold_filters),
            parse=lambda payload: EventCountByDate.model_validate(payload),
        )
        hot_counts = self._hot.get_event_counts_by_date(country_code, hot_filters)
        return self._merge_counts(hot_counts, cold_counts)

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
        route = self._route_for_window(start_date, end_date)

        if route == "hot":
            return self._hot.get_map_aggregations(
                bbox_n, bbox_s, bbox_e, bbox_w, filters, grid_precision
            )

        if route == "cold":
            return self._execute_cold_with_cache(
                method="map_aggregations",
                start_date=start_date,
                end_date=end_date,
                country_code=filters.country_code,
                extra={
                    "event_root_code": filters.event_root_code,
                    "bbox": [bbox_n, bbox_s, bbox_e, bbox_w],
                    "grid_precision": grid_precision,
                    "limit": filters.limit,
                },
                fetch=lambda: self._cold.get_map_aggregations(
                    bbox_n, bbox_s, bbox_e, bbox_w, filters, grid_precision
                ),
                parse=lambda payload: MapAggregation.model_validate(payload),
            )

        cutoff = self._cutoff_date()
        cold_filters = filters.model_copy(update={"start_date": start_date, "end_date": cutoff - timedelta(days=1)})
        hot_filters = filters.model_copy(update={"start_date": cutoff, "end_date": end_date})

        cold_rows = self._execute_cold_with_cache(
            method="map_aggregations",
            start_date=cold_filters.start_date,
            end_date=cold_filters.end_date,
            country_code=filters.country_code,
            extra={
                "event_root_code": filters.event_root_code,
                "bbox": [bbox_n, bbox_s, bbox_e, bbox_w],
                "grid_precision": grid_precision,
                "limit": filters.limit,
                "span": True,
            },
            fetch=lambda: self._cold.get_map_aggregations(
                bbox_n, bbox_s, bbox_e, bbox_w, cold_filters, grid_precision
            ),
            parse=lambda payload: MapAggregation.model_validate(payload),
        )
        hot_rows = self._hot.get_map_aggregations(
            bbox_n, bbox_s, bbox_e, bbox_w, hot_filters, grid_precision
        )
        return self._merge_aggregations(hot_rows, cold_rows)

    def get_event_details(
        self,
        bbox_n: float,
        bbox_s: float,
        bbox_e: float,
        bbox_w: float,
        filters: EventFilter,
    ) -> list[MapEventDetail]:
        start_date, end_date = self._resolve_dates(filters)
        route = self._route_for_window(start_date, end_date)

        if route == "hot":
            return self._hot.get_event_details(bbox_n, bbox_s, bbox_e, bbox_w, filters)

        if route == "cold":
            return self._execute_cold_with_cache(
                method="map_event_details",
                start_date=start_date,
                end_date=end_date,
                country_code=filters.country_code,
                extra={
                    "event_root_code": filters.event_root_code,
                    "bbox": [bbox_n, bbox_s, bbox_e, bbox_w],
                    "limit": filters.limit,
                },
                fetch=lambda: self._cold.get_event_details(
                    bbox_n, bbox_s, bbox_e, bbox_w, filters
                ),
                parse=lambda payload: MapEventDetail.model_validate(payload),
            )

        cutoff = self._cutoff_date()
        cold_filters = filters.model_copy(update={"start_date": start_date, "end_date": cutoff - timedelta(days=1)})
        hot_filters = filters.model_copy(update={"start_date": cutoff, "end_date": end_date})

        cold_rows = self._execute_cold_with_cache(
            method="map_event_details",
            start_date=cold_filters.start_date,
            end_date=cold_filters.end_date,
            country_code=filters.country_code,
            extra={
                "event_root_code": filters.event_root_code,
                "bbox": [bbox_n, bbox_s, bbox_e, bbox_w],
                "limit": filters.limit,
                "span": True,
            },
            fetch=lambda: self._cold.get_event_details(
                bbox_n, bbox_s, bbox_e, bbox_w, cold_filters
            ),
            parse=lambda payload: MapEventDetail.model_validate(payload),
        )
        hot_rows = self._hot.get_event_details(bbox_n, bbox_s, bbox_e, bbox_w, hot_filters)

        merged = hot_rows + cold_rows
        merged.sort(key=lambda row: (row.sql_date, row.global_event_id), reverse=True)
        limit = filters.limit or self._settings.default_query_limit
        return merged[:limit]

    def get_event_by_id(self, event_id: int) -> Event | None:
        event = self._hot.get_event_by_id(event_id)
        if event is not None:
            return event
        return self._cold.get_event_by_id(event_id)

    # ------------------------------------------------------------------
    # Policy and cache helpers
    # ------------------------------------------------------------------

    def _resolve_dates(self, filters: EventFilter) -> tuple[date, date]:
        end_date = filters.end_date or date.today()
        start_date = filters.start_date or (end_date - timedelta(days=self._settings.default_lookback_days))
        if start_date > end_date:
            raise ColdTierPolicyError("Invalid date range: start_date cannot be after end_date.")
        return start_date, end_date

    def _cutoff_date(self) -> date:
        return date.today() - timedelta(days=self._settings.hot_tier_cutoff_days)

    def _route_for_window(self, start_date: date, end_date: date) -> str:
        cutoff = self._cutoff_date()
        if start_date >= cutoff:
            return "hot"
        if end_date < cutoff:
            return "cold"
        return "hybrid"

    def _validate_cold_window(self, start_date: date, end_date: date) -> None:
        window_days = (end_date - start_date).days + 1
        if window_days > self._settings.cold_tier_max_window_days:
            raise ColdTierPolicyError(
                "Cold-tier query rejected: date window exceeds "
                f"{self._settings.cold_tier_max_window_days} days."
            )

    def _load_cold_counts(self) -> dict[str, dict[str, int]]:
        if not self._counter_file.exists():
            return {}
        try:
            return json.loads(self._counter_file.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("cold_query_counter_read_failed", path=str(self._counter_file))
            return {}

    def _persist_cold_counts(self) -> None:
        self._counter_file.write_text(
            json.dumps(self._cold_counts, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )

    def _enforce_and_record_cold_quota(self) -> None:
        user_id = get_request_user_id() or "anonymous"
        month_key = date.today().strftime("%Y-%m")

        with self._counter_lock:
            month_counts = self._cold_counts.setdefault(month_key, {})
            current = int(month_counts.get(user_id, 0))
            if current >= self._settings.cold_tier_monthly_query_limit:
                raise ColdTierPolicyError(
                    "Cold-tier query rejected: monthly user limit reached "
                    f"({self._settings.cold_tier_monthly_query_limit})."
                )

            month_counts[user_id] = current + 1
            self._persist_cold_counts()

    def _cache_file_path(
        self,
        method: str,
        start_date: date,
        end_date: date,
        country_code: str | None,
        extra: dict,
    ) -> Path:
        country = (country_code or "ALL").upper()
        digest = hashlib.sha1(
            json.dumps(extra, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        filename = (
            f"{country}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            f"_{method}_{digest}.parquet"
        )
        return self._cache_dir / filename

    def _load_cache(self, path: Path) -> list[dict]:
        try:
            cached = pd.read_parquet(path)
            payloads = cached.get("payload", [])
            return [json.loads(item) for item in payloads]
        except Exception:
            logger.warning("cold_cache_read_failed", cache_file=str(path))
            return []

    def _save_cache(self, path: Path, rows: list[dict]) -> None:
        payload = [json.dumps(row, separators=(",", ":"), default=str) for row in rows]
        df = pd.DataFrame({"payload": payload})
        df.to_parquet(path, index=False)

    def _execute_cold_with_cache(
        self,
        method: str,
        start_date: date,
        end_date: date,
        country_code: str | None,
        extra: dict,
        fetch: Callable[[], list[T]],
        parse: Callable[[dict], T],
    ) -> list[T]:
        cache_file = self._cache_file_path(method, start_date, end_date, country_code, extra)
        if cache_file.exists():
            cached_rows = self._load_cache(cache_file)
            return [parse(payload) for payload in cached_rows]

        self._validate_cold_window(start_date, end_date)
        self._enforce_and_record_cold_quota()

        rows = fetch()
        serialized = [row.model_dump(mode="json") for row in rows]
        self._save_cache(cache_file, serialized)
        return rows

    @staticmethod
    def _merge_aggregations(
        left: list[MapAggregation],
        right: list[MapAggregation],
    ) -> list[MapAggregation]:
        merged: dict[tuple[float, float], float] = {}
        for row in left + right:
            key = (row.lat, row.lon)
            merged[key] = merged.get(key, 0.0) + float(row.intensity)

        return [
            MapAggregation(lat=lat, lon=lon, intensity=intensity)
            for (lat, lon), intensity in merged.items()
        ]

    @staticmethod
    def _merge_counts(
        left: list[EventCountByDate],
        right: list[EventCountByDate],
    ) -> list[EventCountByDate]:
        state: dict[date, dict[str, float]] = {}

        for row in left + right:
            item = state.setdefault(
                row.date,
                {
                    "count": 0.0,
                    "total_mentions": 0.0,
                    "goldstein_weighted": 0.0,
                    "goldstein_weight": 0.0,
                    "tone_weighted": 0.0,
                    "tone_weight": 0.0,
                },
            )
            count = float(row.count)
            item["count"] += count
            item["total_mentions"] += float(row.total_mentions)

            if row.avg_goldstein_scale is not None:
                item["goldstein_weighted"] += float(row.avg_goldstein_scale) * count
                item["goldstein_weight"] += count

            if row.avg_tone is not None:
                item["tone_weighted"] += float(row.avg_tone) * count
                item["tone_weight"] += count

        merged_rows: list[EventCountByDate] = []
        for day in sorted(state.keys()):
            item = state[day]
            avg_goldstein = None
            if item["goldstein_weight"] > 0:
                avg_goldstein = item["goldstein_weighted"] / item["goldstein_weight"]

            avg_tone = None
            if item["tone_weight"] > 0:
                avg_tone = item["tone_weighted"] / item["tone_weight"]

            merged_rows.append(
                EventCountByDate(
                    date=day,
                    count=int(item["count"]),
                    total_mentions=int(item["total_mentions"]),
                    avg_goldstein_scale=avg_goldstein,
                    avg_tone=avg_tone,
                )
            )

        return merged_rows
