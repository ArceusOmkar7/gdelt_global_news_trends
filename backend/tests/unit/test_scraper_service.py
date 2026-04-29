from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from backend.infrastructure.config.settings import Settings
from backend.infrastructure.services import scraper_service as scraper_module
from backend.infrastructure.services.scraper_service import ScraperService, ScraperError
from backend.domain.models.event import ExtractedArticle


class _FakeDatasetClient:
    def __init__(self, items):
        self._items = items

    async def list_items(self, **kwargs):
        return SimpleNamespace(items=self._items)


class _FakeActorClient:
    def __init__(self, run):
        self.run = run
        self.calls: list[dict] = []

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        return self.run


class _FakeApifyClient:
    def __init__(self, run, items):
        self.actor_client = _FakeActorClient(run)
        self.dataset_client = _FakeDatasetClient(items)

    def actor(self, actor_id):
        self.actor_id = actor_id
        return self.actor_client

    def dataset(self, dataset_id):
        self.dataset_id = dataset_id
        return self.dataset_client


@pytest.fixture
def settings(tmp_path):
    return Settings(
        gcp_project_id="test-project",
        apify_api_token="test-apify-token",
        apify_actor_id="apify/web-scraper",
        scraper_timeout_seconds=30,
        hot_tier_path=str(tmp_path / "hot"),
        cache_path=str(tmp_path / "cache"),
    )


@pytest.mark.asyncio
async def test_scraper_service_fast_path_success(monkeypatch, settings):
    """Test fast path extraction via httpx + BeautifulSoup."""
    html_content = """
    <html>
        <head>
            <title>Test Article</title>
            <meta property="og:image" content="https://example.com/image.jpg" />
        </head>
        <body>
            <article>
                <p>First paragraph of the article.</p>
                <p>Second paragraph with more content.</p>
                <img src="https://example.com/photo.jpg" />
                <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
            </article>
        </body>
    </html>
    """

    # Mock ApifyClientAsync first
    fake_apify = MagicMock()
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", MagicMock(return_value=fake_apify))

    mock_response = MagicMock()
    mock_response.text = html_content
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Test Article"
    assert "First paragraph" in result.text
    assert "Second paragraph" in result.text
    assert "https://example.com/image.jpg" in result.images
    assert any("youtube.com" in embed for embed in result.embeds)



@pytest.mark.asyncio
async def test_scraper_service_fast_path_timeout_fallback_to_apify(monkeypatch, settings):
    """Test that timeout in fast path triggers fallback to Apify."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    fake_run = SimpleNamespace(status="SUCCEEDED", default_dataset_id="dataset-1")
    fake_apify = _FakeApifyClient(fake_run, [{
        "title": "Article from Apify",
        "text": "Content scraped via Apify",
        "images": ["https://apify.com/img1.jpg"],
        "embeds": ["https://youtube.com/embed/123"],
    }])
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", lambda token: fake_apify)

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Article from Apify"
    assert "Content scraped via Apify" in result.text
    assert "https://apify.com/img1.jpg" in result.images
    assert "https://youtube.com/embed/123" in result.embeds


@pytest.mark.asyncio
async def test_scraper_service_apify_success_with_structured_data(monkeypatch, settings):
    """Test Apify extraction with structured media data."""
    fake_run = SimpleNamespace(status="SUCCEEDED", default_dataset_id="dataset-1")
    fake_apify = _FakeApifyClient(fake_run, [{
        "title": "Breaking News",
        "text": "Article body with multiple paragraphs.",
        "images": [
            "https://news.com/img1.jpg",
            "https://news.com/img2.jpg",
        ],
        "embeds": [
            "https://www.youtube.com/embed/abc123",
            "https://vimeo.com/456789",
        ],
    }])
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", lambda token: fake_apify)

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Breaking News"
    assert result.text == "Article body with multiple paragraphs."
    assert len(result.images) == 2
    assert len(result.embeds) == 2


@pytest.mark.asyncio
async def test_scraper_service_both_paths_fail_raises_error(monkeypatch, settings):
    """Test that ScraperError is raised when both fast and slow paths fail."""
    # Mock ApifyClientAsync first
    fake_run = SimpleNamespace(status="FAILED", default_dataset_id=None)
    fake_apify = _FakeApifyClient(fake_run, [])
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", MagicMock(return_value=fake_apify))

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    service = ScraperService(settings)

    with pytest.raises(ScraperError):
        await service.scrape_article("https://example.com/article")


@pytest.mark.asyncio
async def test_scraper_service_fast_path_bot_blocking_fallback(monkeypatch, settings):
    """Test that 403 (bot-blocking) in fast path triggers Apify fallback."""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    fake_run = SimpleNamespace(status="SUCCEEDED", default_dataset_id="dataset-1")
    fake_apify = _FakeApifyClient(fake_run, [{
        "title": "Apify Success",
        "text": "Successfully scraped via Apify despite bot-blocking.",
        "images": [],
        "embeds": [],
    }])
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", lambda token: fake_apify)

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert isinstance(result, ExtractedArticle)
    assert result.title == "Apify Success"


@pytest.mark.asyncio
async def test_scraper_service_text_truncation(monkeypatch, settings):
    """Test that extracted text is truncated to max_chars."""
    # Mock ApifyClientAsync first
    fake_apify = MagicMock()
    monkeypatch.setattr(scraper_module, "ApifyClientAsync", MagicMock(return_value=fake_apify))

    long_text = "Word " * 3000  # ~15k chars, exceeds max of 10k

    html_content = f"<html><body><article><p>{long_text}</p></article></body></html>"

    mock_response = MagicMock()
    mock_response.text = html_content
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    monkeypatch.setattr(scraper_module.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    service = ScraperService(settings)
    result = await service.scrape_article("https://example.com/article")

    assert len(result.text) <= 10003  # 10000 + len("...")
    assert result.text.endswith("...")

