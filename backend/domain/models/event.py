"""Domain models — pure data structures with no I/O or infrastructure imports.

These models represent the core business entities of the GNIEM system.
They are used across all layers (domain → application → API mapping).
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from pydantic import BaseModel, Field


class EventCluster(BaseModel):
    """A cluster of semantically related events.
    
    This is a prototype implementation. Future iterations will use
    actual article text for clustering instead of synthetic features.
    """

    cluster_id: int = Field(description="Zero-indexed cluster identifier.")
    label: str = Field(description="Auto-generated descriptive label for the cluster.")
    event_count: int = Field(description="Number of events in this cluster.")
    avg_goldstein_scale: float | None = Field(
        default=None,
        description="Average Goldstein scale of events in this cluster.",
    )
    top_country_codes: list[str] = Field(
        default_factory=list,
        description="Most frequent country codes in the cluster.",
    )
    top_event_codes: list[str] = Field(
        default_factory=list,
        description="Most frequent CAMEO event codes in the cluster.",
    )
    event_ids: list[int] = Field(
        default_factory=list,
        description="List of global_event_ids belonging to this cluster.",
    )

    model_config = {"frozen": True}


class ForecastPoint(BaseModel):
    """A single predicted data point in a time-series forecast."""

    date: _dt.date = Field(description="The future date being forecasted.")
    predicted_count: float = Field(description="The predicted number of events.")
    lower_bound: float | None = Field(
        default=None,
        description="Lower bound of the confidence interval.",
    )
    upper_bound: float | None = Field(
        default=None,
        description="Upper bound of the confidence interval.",
    )

    model_config = {"frozen": True}


class ForecastResult(BaseModel):
    """The complete result of a time-series forecasting operation."""

    country_code: str | None = Field(
        default=None,
        description="The country code this forecast applies to, or None for global.",
    )
    horizon_days: int = Field(description="Number of days forecasted into the future.")
    model_type: str = Field(description="The underlying algorithm used (e.g., 'prophet').")
    historical_summary: dict = Field(
        default_factory=dict,
        description="Basic statistics about the training data.",
    )
    predictions: list[ForecastPoint] = Field(
        description="The forecasted data points, ordered by date ascending.",
    )

    model_config = {"frozen": True}


class Event(BaseModel):
    """A single GDELT event record.

    Maps the key columns from ``bigquery-public-data.gdelt_2_events.events``
    into a typed, validated Python object.
    """

    global_event_id: int = Field(description="Unique GDELT event identifier.")
    sql_date: _dt.date = Field(description="Date the event was recorded (YYYYMMDD).")
    actor1_country_code: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2/3 code for the first actor's country.",
    )
    actor2_country_code: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2/3 code for the second actor's country.",
    )
    event_root_code: str | None = Field(
        default=None,
        description="CAMEO root event code (2-digit top-level category).",
    )
    event_code: str | None = Field(
        default=None,
        description="Full CAMEO event code.",
    )
    goldstein_scale: float | None = Field(
        default=None,
        description="Goldstein conflict/cooperation score (-10 to +10).",
    )
    num_mentions: int = Field(
        default=0,
        description="Number of mentions of this event across all source documents.",
    )
    num_sources: int = Field(
        default=0,
        description="Number of distinct source URLs mentioning this event.",
    )
    avg_tone: float | None = Field(
        default=None,
        description="Average tone of all documents mentioning this event.",
    )
    action_geo_country_code: str | None = Field(
        default=None,
        description="Country code where the event action took place.",
    )
    action_geo_lat: float | None = Field(
        default=None,
        description="Latitude of the event action location.",
    )
    action_geo_long: float | None = Field(
        default=None,
        description="Longitude of the event action location.",
    )
    source_url: str | None = Field(
        default=None,
        description="URL of the first source document.",
    )

    model_config = {"frozen": True}


class EventFilter(BaseModel):
    """Query filter parameters for retrieving events.

    Used by the application layer to pass validated, typed filters
    into the repository without leaking HTTP concerns.
    """

    start_date: _dt.date | None = Field(
        default=None,
        description="Inclusive start date. Defaults to (today - lookback_days) at query time.",
    )
    end_date: _dt.date | None = Field(
        default=None,
        description="Inclusive end date. Defaults to today at query time.",
    )
    country_code: str | None = Field(
        default=None,
        max_length=3,
        description="Filter by actor1 or action-geo country code.",
    )
    event_root_code: str | None = Field(
        default=None,
        max_length=2,
        description="Filter by CAMEO root event code.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=100_000,
        description="Maximum number of rows to return.",
    )


class EventCountByDate(BaseModel):
    """Aggregated event statistics for a single date.

    Used to power time-series charts on the frontend (Level 2 dashboard).
    """

    date: _dt.date = Field(description="The date of aggregation.")
    count: int = Field(description="Total number of events on this date.")
    avg_goldstein_scale: float | None = Field(
        default=None,
        description="Average Goldstein score for events on this date.",
    )
    total_mentions: int = Field(
        default=0,
        description="Sum of NumMentions across all events on this date.",
    )
    avg_tone: float | None = Field(
        default=None,
        description="Average tone across all events on this date.",
    )

    model_config = {"frozen": True}


class MapAggregation(BaseModel):
    """Geospatial aggregation for low zoom levels."""
    
    lat: float = Field(description="Rounded latitude of the aggregated grid cell.")
    lon: float = Field(description="Rounded longitude of the aggregated grid cell.")
    intensity: float = Field(description="Aggregated intensity, typically event count.")

    model_config = {"frozen": True}


class MapEventDetail(BaseModel):
    """Details for a single event displayed at high zoom levels."""
    
    global_event_id: int
    sql_date: _dt.date
    lat: float
    lon: float
    actor1_country_code: str | None = None
    actor2_country_code: str | None = None
    event_root_code: str | None = None
    goldstein_scale: float | None = None
    num_mentions: int = 0
    num_sources: int = 0
    avg_tone: float | None = None
    source_url: str | None = None
    actor1_type: str | None = None
    actor2_type: str | None = None
    gkg_record_id: str | None = Field(default=None, description="Global Knowledge Graph ID if joined.")

    model_config = {"frozen": True}


class EventAnalysis(BaseModel):
    """LLM-generated intelligence analysis for a news article."""
    
    summary: str = Field(description="A concise summary of the event.")
    sentiment: str = Field(description="Overall sentiment (Positive, Neutral, Negative).")
    entities: list[str] = Field(default_factory=list, description="Key entities mentioned (people, orgs, places).")
    themes: list[str] = Field(default_factory=list, description="Thematic categories detected.")
    confidence: float = Field(description="LLM's confidence in the analysis (0.0 to 1.0).")

    model_config = {"frozen": True}
