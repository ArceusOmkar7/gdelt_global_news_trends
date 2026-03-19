"""Application settings — single source of truth for all configuration.

Reads from environment variables with sensible defaults for local development.
Uses Pydantic BaseSettings for automatic env-var parsing and validation.
"""

import json as _json

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration for the GNIEM backend.

    All values are read from environment variables. A `.env` file in the
    project root is loaded automatically when present.
    """

    # --- GCP / BigQuery ---
    gcp_project_id: str = Field(
        ...,
        description="Google Cloud project ID used for BigQuery billing.",
    )
    google_application_credentials: str | None = Field(
        default=None,
        description=(
            "Path to the GCP service account JSON key file. "
            "If None, Application Default Credentials (ADC) are used."
        ),
    )
    gdelt_dataset: str = Field(
        default="gdelt-bq.gdeltv2",
        description="Fully-qualified BigQuery dataset for GDELT 2.1.",
    )
    gdelt_table: str = Field(
        default="events",
        description="Table name within the GDELT dataset.",
    )
    hot_tier_path: str = Field(
        default="/data/hot_tier",
        description="Local directory path containing hot-tier Parquet files.",
    )
    cache_path: str = Field(
        default="/data/cache",
        description="Local directory path for cached query artifacts and counters.",
    )
    bq_max_scan_bytes: int = Field(
        default=2_000_000_000,
        ge=1,
        description=(
            "Maximum allowed BigQuery bytes scanned for a single query. "
            "Queries above this threshold are aborted after dry run."
        ),
    )
    hot_tier_cutoff_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Requests newer than this many days use hot-tier DuckDB.",
    )
    cold_tier_max_window_days: int = Field(
        default=30,
        ge=1,
        le=180,
        description="Maximum allowed cold-tier date window in days.",
    )
    cold_tier_monthly_query_limit: int = Field(
        default=3,
        ge=1,
        le=100,
        description="Maximum cold-tier queries allowed per user per month.",
    )

    # --- AI / LLM ---
    llm_model_name: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model to use for analysis (e.g., gemini-1.5-flash, gemini-1.5-pro).",
    )
    groq_api_key: str | None = Field(
        default=None,
        description="Optional Groq API key used by nightly briefing precompute jobs.",
    )

    # --- Query Defaults ---
    default_lookback_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Default number of days to look back when no date range is specified.",
    )
    default_query_limit: int = Field(
        default=10_000,
        ge=1,
        le=100_000,
        description="Maximum number of rows returned by a single query.",
    )

    # --- Application ---
    environment: str = Field(
        default="development",
        description="Runtime environment: development | staging | production.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="URL prefix for the v1 API.",
    )
    # Stored as a plain string to avoid pydantic-settings JSON decode issues.
    # Use the `cors_origins` property for the parsed list.
    cors_origins_raw: str = Field(
        default='["http://localhost:3000","http://localhost:5173","http://127.0.0.1:5173"]',
        alias="CORS_ORIGINS",
        description="Allowed CORS origins (JSON array string or comma-separated).",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parse cors_origins_raw into a list of origin strings."""
        if self.environment == "development":
            return ["*"]
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError:
                inner = raw.strip("[]")
                return [s.strip().strip("\"'") for s in inner.split(",") if s.strip()]
        return [s.strip() for s in raw.split(",") if s.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "populate_by_name": True,
        "extra": "ignore",
    }


# Module-level singleton — import this instance everywhere.
# In tests, override via FastAPI dependency injection.
settings = Settings()
