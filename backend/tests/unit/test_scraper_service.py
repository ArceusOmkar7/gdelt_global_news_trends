from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.domain.models.event import ExtractedArticle
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.services import scraper_service as scraper_module
from backend.infrastructure.services.scraper_service import ScraperError, ScraperService


@pytest.fixture
def settings(tmp_path):
    return Settings(
        gcp_project_id="test-project",
        hot_tier_path=str(tmp_path / "hot"),
        cache_path=str(tmp_path / "cache"),
    )


def _mock_async_client(monkeypatch, response):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=response)
    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))


@pytest.mark.asyncio
async def test_scraper_service_jina_success_extracts_media_and_embeds(monkeypatch, settings):
    content_text = (
        "This is a long enough article body to pass the minimum content threshold. "
        "It includes an external embed link to ensure URL extraction works. "
        "https://vimeo.com/1234567"
    )
    payload = {
        "data": {
            "title": "Test Article",
            "content": content_text,
            "images": [
                {"url": "https://example.com/images/logo.png"},
                {"url": "https://cdn.example.com/photos/story.jpg"},
                {"url": "https://example.com/icon.svg"},
                {"url": "https://example.com/photo.jpg?w=32&h=32"},
            ],
            "links": {
                "YouTube": "https://www.youtube.com/watch?v=abc",
                "News": "https://news.example.com/article",
            },
        }
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=payload)
    _mock_async_client(monkeypatch, mock_response)

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Test Article"
    assert "long enough article body" in result.text
    assert result.images == ["https://cdn.example.com/photos/story.jpg"]
    assert "https://www.youtube.com/embed/abc" in result.embeds
    assert "https://player.vimeo.com/video/1234567" in result.embeds


@pytest.mark.asyncio
async def test_scraper_service_jina_timeout(monkeypatch, settings):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    service = ScraperService(settings)
    with pytest.raises(ScraperError):
        await service.scrape_article("https://example.com/article")


@pytest.mark.asyncio
async def test_scraper_service_jina_http_error(monkeypatch, settings):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_response)
    )
    _mock_async_client(monkeypatch, mock_response)

    service = ScraperService(settings)
    with pytest.raises(ScraperError):
        await service.scrape_article("https://example.com/article")


@pytest.mark.asyncio
async def test_scraper_service_text_truncation(monkeypatch, settings):
    long_text = "Word " * 3000
    payload = {"data": {"title": "Long Article", "content": long_text}}

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=payload)
    _mock_async_client(monkeypatch, mock_response)

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert len(result.text) <= scraper_module.MAX_CHARS + 3
    assert result.text.endswith("...")

