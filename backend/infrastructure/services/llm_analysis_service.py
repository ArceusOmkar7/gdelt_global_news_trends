"""LLM analysis service — implements ILLMAnalysisService using Groq.

Uses Groq-hosted models to perform deep intelligence analysis on news article text.
"""

from __future__ import annotations

import structlog

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    AsyncGroq = None  # type: ignore[assignment]

from backend.domain.models.event import EventAnalysis
from backend.domain.ports.ports import ILLMAnalysisService
from backend.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


class LLMAnalysisService(ILLMAnalysisService):
    """Groq implementation of the LLM analysis service."""

    def __init__(self, settings: Settings) -> None:
        if AsyncGroq is None:
            raise RuntimeError("groq is required for LLM analysis but is not installed")
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required for LLM analysis")

        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._model_name = settings.groq_model_name

    async def analyze_event(self, article_text: str) -> EventAnalysis:
        """Analyze article text and return structured intelligence."""
        logger.info("llm_analysis_start", text_length=len(article_text))

        try:
            completion = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a structured intelligence analyst. "
                            "Return only JSON with keys: summary, sentiment, entities, themes, confidence. "
                            "Sentiment must be one of Positive, Neutral, or Negative."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Analyze the following news article text and provide a concise intelligence report.\n\n"
                            f"Article Text:\n---\n{article_text}\n---"
                        ),
                    },
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = completion.choices[0].message.content if completion.choices else None
            if not content:
                raise RuntimeError("Groq returned an empty completion")

            analysis = EventAnalysis.model_validate_json(content)
            
            logger.info("llm_analysis_success", sentiment=analysis.sentiment)
            return analysis
            
        except Exception as exc:
            logger.error("llm_analysis_failed", error=str(exc))
            raise
