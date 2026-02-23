"""API schemas — request/response models for the HTTP layer.

These are separate from domain models to decouple serialisation concerns
from business logic.  The API layer maps between these schemas and domain
models — domain models never leak directly into HTTP responses.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EventFilterRequest(BaseModel):
    """Query parameters for the GET /events endpoint."""

    start_date: date | None = Field(
        default=None,
        description="Inclusive start date (YYYY-MM-DD). Defaults to 7 days ago.",
    )
    end_date: date | None = Field(
        default=None,
        description="Inclusive end date (YYYY-MM-DD). Defaults to today.",
    )
    country_code: str | None = Field(
        default=None,
        max_length=3,
        description="ISO country code filter (e.g., US, IRQ).",
    )
    event_root_code: str | None = Field(
        default=None,
        max_length=2,
        description="CAMEO root event code filter.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=100_000,
        description="Maximum number of records to return.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class EventResponse(BaseModel):
    """Serialised representation of a single GDELT event."""

    global_event_id: int
    sql_date: date
    actor1_country_code: str | None = None
    actor2_country_code: str | None = None
    event_root_code: str | None = None
    event_code: str | None = None
    goldstein_scale: float | None = None
    num_mentions: int = 0
    num_articles: int = 0
    num_sources: int = 0
    avg_tone: float | None = None
    action_geo_country_code: str | None = None
    action_geo_lat: float | None = None
    action_geo_long: float | None = None
    source_url: str | None = None


class EventListResponse(BaseModel):
    """Paginated list of events."""

    count: int = Field(description="Number of events in this response.")
    data: list[EventResponse] = Field(description="List of event records.")


class EventCountResponse(BaseModel):
    """Daily-aggregated event statistics for charting."""

    date: date
    count: int
    avg_goldstein_scale: float | None = None
    total_mentions: int = 0
    total_articles: int = 0
    avg_tone: float | None = None


class EventCountListResponse(BaseModel):
    """List of daily event counts."""

    count: int = Field(description="Number of date records.")
    data: list[EventCountResponse] = Field(description="Daily aggregated counts.")


class EventClusterResponse(BaseModel):
    """Serialised representation of an event cluster."""

    cluster_id: int
    label: str
    event_count: int
    avg_goldstein_scale: float | None = None
    top_country_codes: list[str] = Field(default_factory=list)
    top_event_codes: list[str] = Field(default_factory=list)
    event_ids: list[int] = Field(default_factory=list)


class ClusterListResponse(BaseModel):
    """List of event clusters."""

    count: int = Field(description="Number of clusters in this response.")
    data: list[EventClusterResponse] = Field(description="List of cluster records.")


class ForecastPointResponse(BaseModel):
    """Serialised representation of a forecasted data point."""

    date: date
    predicted_count: float
    lower_bound: float | None = None
    upper_bound: float | None = None


class ForecastResponse(BaseModel):
    """Serialised time-series forecast result."""

    country_code: str | None = None
    horizon_days: int
    model_type: str
    historical_summary: dict = Field(default_factory=dict)
    predictions: list[ForecastPointResponse]


class BigQueryHealthDetail(BaseModel):
    """Nested detail for BigQuery connectivity in health check."""

    connected: bool
    project: str
    dataset: str
    latency_ms: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health-check response with comprehensive service diagnostics."""

    status: str = Field(description="Overall service status: healthy | degraded | unhealthy.")
    environment: str = Field(description="Runtime environment (development, staging, production).")
    version: str = Field(description="Application version string.")
    bigquery: BigQueryHealthDetail = Field(description="BigQuery connection details.")
    uptime_seconds: float = Field(description="Seconds since the application started.")
