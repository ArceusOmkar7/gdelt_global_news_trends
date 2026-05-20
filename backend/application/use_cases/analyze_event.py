"""Use case — on-demand deep intelligence analysis for a single event.

Orchestrates the scraper service and the LLM analysis service to provide
deeper context than what is available in the raw GDELT records.
"""

from __future__ import annotations

import structlog

from backend.domain.models.event import EventAnalysis, EntityGroup
from backend.domain.ports.ports import IEventRepository, ILLMAnalysisService
from backend.infrastructure.services.scraper_service import ScraperService

logger = structlog.get_logger(__name__)


class AnalyzeEventUseCase:
    """Application-layer orchestrator for event-level intelligence analysis."""

    def __init__(
        self,
        repository: IEventRepository,
        scraper: ScraperService,
        llm: ILLMAnalysisService,
    ) -> None:
        self._repository = repository
        self._scraper = scraper
        self._llm = llm

    async def execute(self, event_id: int) -> EventAnalysis:
        """Fetch an event's source URL, scrape its content, and analyze it.

        Args:
            event_id: The GLOBALEVENTID of the event to analyze.

        Returns:
            An EventAnalysis object containing summary, entities, sentiment, and media.
        """
        logger.info("analyze_event_execute_start", event_id=event_id)
        
        # 1. Fetch event from repository to get source_url
        event = self._repository.get_event_by_id(event_id)
        
        if not event or not event.source_url:
            logger.warning("analyze_event_missing_source", event_id=event_id)
            return EventAnalysis(
                summary="Source URL not available for this event.",
                sentiment="Neutral",
                entities=EntityGroup(),
                themes=[],
                confidence=0.0,
                images=[],
                embeds=[],
            )

        # 2. Scrape article content and media
        try:
            extracted = await self._scraper.scrape_article(event.source_url)
        except Exception as e:
            logger.error("analyze_event_scrape_failed", event_id=event_id, error=str(e))
            return EventAnalysis(
                summary=f"Failed to scrape article from source URL: {event.source_url}.",
                sentiment="Neutral",
                entities=EntityGroup(),
                themes=[],
                confidence=0.0,
                images=[],
                embeds=[],
            )

        # 3. Perform LLM analysis on the extracted text
        analysis = await self._llm.analyze_event(extracted.text)
        
        # 4. Inject media data from the scraper into the analysis
        # This keeps media separate from LLM processing, avoiding hallucinations
        analysis_with_media = EventAnalysis(
            summary=analysis.summary,
            sentiment=analysis.sentiment,
            entities=analysis.entities,
            themes=analysis.themes,
            confidence=analysis.confidence,
            images=extracted.images,
            embeds=extracted.embeds,
        )
        
        logger.info("analyze_event_execute_success", event_id=event_id)
        return analysis_with_media

