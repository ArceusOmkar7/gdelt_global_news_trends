"""Unit tests for configuration Settings."""

import os
from pydantic import ValidationError
import pytest

from backend.infrastructure.config.settings import Settings

class TestSettings:
    def test_default_settings(self):
        # Requires GCP_PROJECT_ID at minimum if not provided
        settings = Settings(gcp_project_id="test-project")
        assert settings.gcp_project_id == "test-project"
        assert settings.environment == "development"
        assert settings.default_lookback_days == 7
        
    def test_cors_origins_development(self):
        settings = Settings(gcp_project_id="test-project", environment="development")
        assert settings.cors_origins == ["*"]
        
    def test_cors_origins_production_json(self):
        settings = Settings(
            gcp_project_id="test-project", 
            environment="production",
            cors_origins_raw='["https://example.com"]'
        )
        assert settings.cors_origins == ["https://example.com"]
        
    def test_cors_origins_production_csv(self):
        settings = Settings(
            gcp_project_id="test-project", 
            environment="production",
            cors_origins_raw="https://a.com,https://b.com"
        )
        assert settings.cors_origins == ["https://a.com", "https://b.com"]
        
    def test_cors_origins_production_fallback(self):
        settings = Settings(
            gcp_project_id="test-project", 
            environment="production",
            cors_origins_raw=""
        )
        assert settings.cors_origins == []
        
    def test_ensure_required_dirs(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        hot_tier = str(tmp_path / "hot")
        
        # Directories don't exist yet
        assert not os.path.exists(cache_dir)
        assert not os.path.exists(hot_tier)
        
        Settings(
            gcp_project_id="test-project",
            cache_path=cache_dir,
            hot_tier_path=hot_tier
        )
        
        # Should be created by the validator
        assert os.path.exists(cache_dir)
        assert os.path.exists(hot_tier)
