"""Scraper service — fetches and cleans article text from source URLs.

Provides a lightweight way to extract the core content from news articles
on-demand for further AI analysis.
"""

from __future__ import annotations

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class ScraperError(Exception):
    """Raised when an article cannot be scraped."""


class ScraperService:
    """Service for extracting text content from news URLs."""

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

    async def scrape_article(self, url: str) -> str:
        """Fetch an article and extract its main text content.

        Args:
            url: The source URL of the article.

        Returns:
            The extracted text content.

        Raises:
            ScraperError: If the request fails or content cannot be parsed.
        """
        logger.info("scraping_article_start", url=url)
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
        except Exception as e:
            logger.error("scraping_article_request_failed", url=url, error=str(e))
            raise ScraperError(f"Failed to fetch URL: {str(e)}") from e

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Focus on paragraphs for cleaner text extraction
            paragraphs = soup.find_all("p")
            text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            
            # Fallback if no paragraphs found
            if not text:
                text = soup.get_text(separator="\n", strip=True)

            # Basic truncation if extremely long
            max_chars = 10000
            if len(text) > max_chars:
                text = text[:max_chars] + "..."

            logger.info("scraping_article_success", url=url, text_length=len(text))
            return text
            
        except Exception as e:
            logger.error("scraping_article_parsing_failed", url=url, error=str(e))
            raise ScraperError(f"Failed to parse article content: {str(e)}") from e
