"""Unit tests for AnalyzeEventUseCase."""

from datetime import date
from unittest.mock import MagicMock, AsyncMock

import pytest

from backend.application.use_cases.analyze_event import AnalyzeEventUseCase
from backend.domain.models.event import Event, EventAnalysis
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
async def test_analyze_event_success(use_case, mock_repo, mock_scraper, mock_llm):
    # Setup
    event_id = 123
    mock_event = Event(
        global_event_id=event_id,
        sql_date=date(2024, 1, 1),
        source_url="http://example.com/news"
    )
    mock_repo.get_event_by_id.return_value = mock_event
    mock_scraper.scrape_article.return_value = "Article content"
    
    expected_analysis = EventAnalysis(
        summary="Test summary",
        sentiment="Positive",
        entities=["Actor A"],
        themes=["Peace"],
        confidence=0.9
    )
    mock_llm.analyze_event.return_value = expected_analysis
    
    # Execute
    result = await use_case.execute(event_id)
    
    # Verify
    assert result == expected_analysis
    mock_repo.get_event_by_id.assert_called_once_with(event_id)
    mock_scraper.scrape_article.assert_called_once_with("http://example.com/news")
    mock_llm.analyze_event.assert_called_once_with("Article content")


@pytest.mark.asyncio
async def test_analyze_event_no_url(use_case, mock_repo, mock_scraper, mock_llm):
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
    mock_scraper.scrape_article.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_event_scrape_failure(use_case, mock_repo, mock_scraper, mock_llm):
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
    mock_llm.analyze_event.assert_not_called()
