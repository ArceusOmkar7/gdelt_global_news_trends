"""Scraper service — extracts article content and media from source URLs.

Implements a hybrid two-tier extraction strategy:
1. Fast Path: httpx + BeautifulSoup for quick metadata extraction (2-3 sec timeout).
2. Slow Path: Apify actor for full content and media extraction (fallback on bot-blocking).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urljoin, urlparse

import structlog
import httpx
from bs4 import BeautifulSoup

try:
    from apify_client import ApifyClientAsync
except ImportError:  # pragma: no cover
    ApifyClientAsync = None  # type: ignore[assignment]

from backend.domain.models.event import ExtractedArticle
from backend.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


class ScraperError(Exception):
    """Raised when an article cannot be scraped."""


class ScraperService:
    """Service for extracting article content and media from news URLs."""

    def __init__(self, settings: Settings) -> None:
        if ApifyClientAsync is None:
            raise RuntimeError("apify-client is required for article extraction but is not installed")
        if not settings.apify_api_token:
            raise RuntimeError("APIFY_API_TOKEN is required for article extraction")

        self._fast_timeout_seconds = 3.0  # Fast path timeout
        self._slow_timeout_seconds = settings.scraper_timeout_seconds
        self._actor_id = settings.apify_actor_id
        self._client = ApifyClientAsync(token=settings.apify_api_token)

    async def scrape_article(self, url: str) -> ExtractedArticle:
        """Fetch an article and extract its content and media.

        Implements a fast-path-first strategy with Apify fallback:
        1. Try fast metadata extraction via httpx + BeautifulSoup (2-3 sec).
        2. If fast path fails or returns insufficient data, fall back to Apify (full scrape).

        Args:
            url: The source URL of the article.

        Returns:
            An ExtractedArticle containing title, text, images, and embeds.

        Raises:
            ScraperError: If both fast and slow paths fail.
        """
        logger.info("scraping_article_start", url=url)
        
        fast_exc = None
        slow_exc = None
        
        # Try fast path first
        try:
            result = await self._scrape_fast_path(url)
            logger.info("scraping_article_fast_path_success", url=url)
            return result
        except Exception as e:
            fast_exc = e
            logger.warning(
                "scraping_article_fast_path_failed",
                url=url,
                error=str(e),
            )

        # If fast path fails, fall back to slow path (Apify)
        logger.info("scraping_article_falling_back_to_slow_path", url=url)
        try:
            result = await self._scrape_slow_path(url)
            logger.info("scraping_article_slow_path_success", url=url)
            return result
        except Exception as e:
            slow_exc = e
            logger.error("scraping_article_slow_path_failed", url=url, error=str(e))
            raise ScraperError(
                f"Both fast and slow scraping paths failed. Fast: {str(fast_exc)}, Slow: {str(slow_exc)}"
            ) from slow_exc

    async def _scrape_fast_path(self, url: str) -> ExtractedArticle:
        """Extract metadata quickly using httpx + BeautifulSoup.

        Targets:
        - <meta> tags (og:image, og:description, og:title, etc.)
        - <title> tag
        - Basic text from <p> tags
        - <img> sources (first few)
        - <iframe> embeds (especially YouTube)

        Args:
            url: The source URL.

        Returns:
            An ExtractedArticle with available metadata.

        Raises:
            ScraperError: If the request fails or parsing is unsuccessful.
        """
        try:
            async with httpx.AsyncClient(timeout=self._fast_timeout_seconds) as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                )
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException:
            raise ScraperError(f"Fast path request timed out after {self._fast_timeout_seconds}s") from None
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                raise ScraperError(f"Bot-blocking detected: {e.response.status_code}") from e
            raise ScraperError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            raise ScraperError(f"Fast path request failed: {str(e)}") from e

        # Parse HTML
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            raise ScraperError(f"Failed to parse HTML: {str(e)}") from e

        # Extract title
        title = self._extract_title(soup)

        # Extract text
        text = self._extract_text_fast(soup)

        # Extract images from meta tags and <img> elements
        images = self._extract_images(soup, url)

        # Extract embeds (YouTube, Vimeo, etc.)
        embeds = self._extract_embeds(soup)

        if not title or not text:
            raise ScraperError("Fast path returned insufficient data (missing title or text)")

        # Truncate text if too long
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return ExtractedArticle(
            title=title,
            text=text,
            images=images,
            embeds=embeds,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from <meta> tags or <title>."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try standard title tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        return "Untitled"

    def _extract_text_fast(self, soup: BeautifulSoup) -> str:
        """Extract main article text from <p> tags and basic structure."""
        # Remove scripts, styles, and other non-content elements
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()

        # Try to find article container
        article = soup.find("article")
        content_container = article or soup.find(class_=["content", "main", "article-body", "post-content"])
        
        if content_container is None:
            content_container = soup.find("body")

        # Extract paragraphs
        paragraphs = []
        if content_container:
            for p in content_container.find_all("p", limit=50):
                text = p.get_text(strip=True)
                if text and len(text) > 20:  # Filter out short fragments
                    paragraphs.append(text)

        # Fall back to all text if no paragraphs found
        if not paragraphs:
            paragraphs = [content_container.get_text(strip=True)] if content_container else []

        return "\n".join(paragraphs).strip()

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract image URLs from meta tags and <img> elements."""
        images = set()

        # Extract from meta tags
        for prop in ["og:image", "twitter:image"]:
            meta = soup.find("meta", property=prop)
            if meta and meta.get("content"):
                img_url = meta["content"].strip()
                if self._is_valid_url(img_url):
                    images.add(img_url)

        # Extract from <img> elements (limit to first 10)
        for img in soup.find_all("img", limit=10):
            src = img.get("src") or img.get("data-src")
            if src:
                # Resolve relative URLs
                if src.startswith("/"):
                    src = urljoin(base_url, src)
                if self._is_valid_url(src) and not src.endswith((".gif", ".svg")):
                    images.add(src)

        return list(images)[:10]  # Limit to 10 images

    def _extract_embeds(self, soup: BeautifulSoup) -> list[str]:
        """Extract embedded media URLs, especially YouTube and Vimeo."""
        embeds = []

        # YouTube embeds
        for iframe in soup.find_all("iframe", limit=5):
            src = iframe.get("src", "")
            if "youtube.com" in src or "youtu.be" in src or "vimeo.com" in src:
                if self._is_valid_url(src):
                    embeds.append(src)

        # Twitter/X embeds
        for twitter in soup.find_all(class_="twitter-tweet"):
            # Extract URL from tweet HTML if available
            link = twitter.find("a")
            if link and link.get("href"):
                embeds.append(link["href"])

        return embeds[:5]  # Limit to 5 embeds

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if a string is a valid URL."""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    async def _scrape_slow_path(self, url: str) -> ExtractedArticle:
        """Fall back to Apify actor for full content extraction.

        Args:
            url: The source URL.

        Returns:
            An ExtractedArticle extracted via Apify.

        Raises:
            ScraperError: If the Apify request fails.
        """
        logger.info("apify_slow_path_start", url=url)

        try:
            actor = self._client.actor(self._actor_id)
            run = await actor.call(
                run_input={
                    "startUrls": [{"url": url}],
                    "maxRequestsPerCrawl": 1,
                    "pageFunction": self._page_function(),
                    "waitForFinish": 5000,
                },
                wait_secs=self._slow_timeout_seconds,
            )
        except Exception as exc:
            logger.error("apify_slow_path_request_failed", url=url, error=str(exc))
            raise ScraperError(f"Failed to fetch URL via Apify: {str(exc)}") from exc

        try:
            if run is None:
                raise ScraperError("Apify actor did not return a run")

            if getattr(run, "status", None) != "SUCCEEDED":
                raise ScraperError(f"Apify actor run did not succeed: {getattr(run, 'status', 'unknown')}")

            dataset_id = getattr(run, "default_dataset_id", None)
            if not dataset_id:
                raise ScraperError("Apify actor run did not return a default dataset")

            dataset_page = await self._client.dataset(dataset_id).list_items(limit=1)
            items = list(dataset_page.items)
            if not items:
                raise ScraperError("Apify actor returned no dataset items")

            item = items[0]
            title = item.get("title", "Untitled")
            text = item.get("text", "")
            images = item.get("images", [])
            embeds = item.get("embeds", [])

            if not text:
                raise ScraperError("Apify actor returned an empty article body")

            # Truncate text if too long
            max_chars = 10000
            if len(text) > max_chars:
                text = text[:max_chars] + "..."

            logger.info("apify_slow_path_success", url=url, text_length=len(text))
            return ExtractedArticle(
                title=title,
                text=text,
                images=images,
                embeds=embeds,
            )
        except ScraperError:
            raise
        except Exception as exc:
            logger.error("apify_slow_path_parsing_failed", url=url, error=str(exc))
            raise ScraperError(f"Failed to parse Apify response: {str(exc)}") from exc

    @staticmethod
    def _page_function() -> str:
        """JavaScript page function for Apify web-scraper actor.

        Extracts structured data: title, text, images, and embeds.
        """
        return """
async ({ request, page }) => {
    // Extract main text content
    const text = await page.evaluate(() => {
        const root = document.querySelector('article') || document.querySelector('main') || document.body;
        if (!root) {
            return '';
        }

        const nodes = Array.from(root.querySelectorAll('h1, h2, h3, h4, h5, h6, p, li'));
        const source = nodes.length > 0 ? nodes : Array.from(root.querySelectorAll('*'));
        const lines = source
            .map((element) => (element.innerText || element.textContent || '').trim())
            .filter(Boolean);
        return lines.join('\\n');
    });

    // Extract images
    const images = await page.evaluate(() => {
        const imageUrls = new Set();
        
        // From meta tags
        ['og:image', 'twitter:image'].forEach(prop => {
            const meta = document.querySelector(`meta[property="${prop}"]`);
            if (meta && meta.content) imageUrls.add(meta.content);
        });
        
        // From img tags
        document.querySelectorAll('img').forEach((img, idx) => {
            if (idx >= 10) return;
            const src = img.src || img.dataset.src;
            if (src && !src.endsWith('.gif') && !src.endsWith('.svg')) {
                imageUrls.add(src);
            }
        });
        
        return Array.from(imageUrls);
    });

    // Extract embeds (YouTube, Vimeo, etc.)
    const embeds = await page.evaluate(() => {
        const embedUrls = [];
        
        // YouTube/Vimeo iframes
        document.querySelectorAll('iframe').forEach((iframe, idx) => {
            if (idx >= 5) return;
            const src = iframe.src || '';
            if (src.includes('youtube.com') || src.includes('youtu.be') || src.includes('vimeo.com')) {
                embedUrls.push(src);
            }
        });
        
        return embedUrls;
    });

    return {
        url: request.url,
        title: await page.title(),
        text,
        images,
        embeds,
    };
}
""".strip()

