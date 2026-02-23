"""LLM analysis service — implements ILLMAnalysisService using Vertex AI.

Uses Google's Gemini models via Vertex AI to perform deep intelligence 
analysis on news article text.
"""

from __future__ import annotations

import json
from pathlib import Path
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
import structlog

from backend.domain.models.event import EventAnalysis
from backend.domain.ports.ports import ILLMAnalysisService
from backend.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


class LLMAnalysisService(ILLMAnalysisService):
    """Vertex AI implementation of the LLM analysis service."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        
        # Load credentials if provided to ensure Vertex AI uses the correct service account
        credentials = None
        creds_path = settings.google_application_credentials
        if creds_path and Path(creds_path).is_file():
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            logger.info("llm_analysis_using_service_account", path=creds_path)

        vertexai.init(
            project=settings.gcp_project_id,
            credentials=credentials
        )
        self._model = GenerativeModel("gemini-1.5-pro")

    async def analyze_event(self, article_text: str) -> EventAnalysis:
        """Analyze article text and return structured intelligence."""
        logger.info("llm_analysis_start", text_length=len(article_text))
        
        prompt = f"""
        Analyze the following news article text and provide a structured intelligence report.
        Focus on identifying the core event, key actors, sentiment, and thematic categories.

        Article Text:
        ---
        {article_text}
        ---

        Return your analysis ONLY as a valid JSON object with the following schema:
        {{
            "summary": "string - a 2-3 sentence summary of the main event",
            "sentiment": "string - one of: Positive, Neutral, Negative",
            "entities": ["string" - list of key people, organizations, or specific locations],
            "themes": ["string" - list of high-level categories like 'Conflict', 'Diplomacy', 'Economy'],
            "confidence": float - your confidence score from 0.0 to 1.0
        }}
        """

        try:
            # Using synchronous call for now as vertexai's async support varies by version
            # In a high-concurrency app, we'd use the async methods if available.
            response = self._model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            
            # Extract JSON from response
            result_json = json.loads(response.text)
            
            analysis = EventAnalysis(
                summary=result_json.get("summary", "No summary available."),
                sentiment=result_json.get("sentiment", "Neutral"),
                entities=result_json.get("entities", []),
                themes=result_json.get("themes", []),
                confidence=result_json.get("confidence", 0.0)
            )
            
            logger.info("llm_analysis_success", sentiment=analysis.sentiment)
            return analysis
            
        except Exception as e:
            logger.error("llm_analysis_failed", error=str(e))
            # Fallback for demonstration/resilience
            return EventAnalysis(
                summary="Analysis failed due to a service error.",
                sentiment="Neutral",
                entities=[],
                themes=[],
                confidence=0.0
            )
