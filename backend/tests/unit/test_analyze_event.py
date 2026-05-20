"""Unit tests for AnalyzeEventUseCase."""

from datetime import date
from unittest.mock import MagicMock, AsyncMock

import pytest

from backend.application.use_cases.analyze_event import AnalyzeEventUseCase
from backend.domain.models.event import Event, EventAnalysis, ExtractedArticle, EntityGroup
from backend.domain.ports.ports import IEventRepository, ILLMAnalysisService
from backend.infrastructure.services.scraper_service import ScraperService


@pytest.fixture
def mock_repo():
    return MagicMock(spec=IEventRepository)


@pytest.fixture
def mock_scraper():
    return AsyncMock(spec=ScraperService)


@pytest.fixture
def mock_llm():
    return AsyncMock(spec=ILLMAnalysisService)


@pytest.fixture
def use_case(mock_repo, mock_scraper, mock_llm):
    return AnalyzeEventUseCase(mock_repo, mock_scraper, mock_llm)


@pytest.mark.asyncio
async def test_analyze_event_success_with_media(use_case, mock_repo, mock_scraper, mock_llm):
    """Test successful event analysis with media data."""
    # Setup
    event_id = 123
    mock_event = Event(
        global_event_id=event_id,
        sql_date=date(2024, 1, 1),
        source_url="http://example.com/news"
    )
    mock_repo.get_event_by_id.return_value = mock_event
    
    extracted = ExtractedArticle(
        title="Article Title",
        text="Article content goes here.",
        images=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
        embeds=["https://youtube.com/embed/abc123"],
    )
    mock_scraper.scrape_article.return_value = extracted
    
    llm_analysis = EventAnalysis(
        summary="Test summary",
        sentiment="Positive",
        entities=EntityGroup(persons=["Actor A"]),
        themes=["Peace"],
        confidence=0.9,
        images=[],  # LLM doesn't provide images
        embeds=[],  # LLM doesn't provide embeds
    )
    mock_llm.analyze_event.return_value = llm_analysis
    
    # Execute
    result = await use_case.execute(event_id)
    
    # Verify: Result should have LLM analysis + scraped media
    assert result.summary == "Test summary"
    assert result.sentiment == "Positive"
    assert len(result.images) == 2
    assert len(result.embeds) == 1
    assert result.images == extracted.images
    assert result.embeds == extracted.embeds
    
    mock_repo.get_event_by_id.assert_called_once_with(event_id)
    mock_scraper.scrape_article.assert_called_once_with("http://example.com/news")
    mock_llm.analyze_event.assert_called_once_with("Article content goes here.")


@pytest.mark.asyncio
async def test_analyze_event_no_url(use_case, mock_repo, mock_scraper, mock_llm):
    """Test handling of missing source URL."""
    # Setup
    event_id = 123
    mock_event = Event(
        global_event_id=event_id,
        sql_date=date(2024, 1, 1),
        source_url=None
    )
    mock_repo.get_event_by_id.return_value = mock_event
    
    # Execute
    result = await use_case.execute(event_id)
    
    # Verify
    assert "Source URL not available" in result.summary
    assert result.images == []
    assert result.embeds == []
    mock_scraper.scrape_article.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_event_scrape_failure(use_case, mock_repo, mock_scraper, mock_llm):
    """Test handling of scraper failures."""
    # Setup
    event_id = 123
    mock_event = Event(
        global_event_id=event_id,
        sql_date=date(2024, 1, 1),
        source_url="http://example.com/bad"
    )
    mock_repo.get_event_by_id.return_value = mock_event
    mock_scraper.scrape_article.side_effect = Exception("Network error")
    
    # Execute
    result = await use_case.execute(event_id)
    
    # Verify
    assert "Failed to scrape" in result.summary
    assert result.images == []
    assert result.embeds == []
    mock_llm.analyze_event.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_event_missing_event(use_case, mock_repo, mock_llm, mock_scraper):
    """Test handling of missing event."""
    # Setup
    event_id = 999
    mock_repo.get_event_by_id.return_value = None
    
    # Execute
    result = await use_case.execute(event_id)
    
    # Verify
    assert "Source URL not available" in result.summary
    assert result.images == []
    assert result.embeds == []
    mock_scraper.scrape_article.assert_not_called()
    mock_llm.analyze_event.assert_not_called()

    mock_llm.analyze_event.assert_not_called()
