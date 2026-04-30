"""Scraper service — extracts article content, images, and embeds via Jina AI Reader."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, urlparse

import httpx
import structlog

from backend.domain.models.event import ExtractedArticle
from backend.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)

JINA_BASE = "https://r.jina.ai/"
JINA_TIMEOUT = 20.0
MAX_CHARS = 8000
MAX_IMAGES = 10
MAX_EMBEDS = 5
MIN_TEXT_CHARS = 100
MIN_IMAGE_SCORE = 1
EMBED_DOMAINS = ("youtube.com", "youtu.be", "vimeo.com", "twitter.com", "x.com", "t.co")
IMAGE_HINT_TOKENS = (
    "feature",
    "featured",
    "hero",
    "cover",
    "article",
    "story",
    "photo",
    "media",
    "main",
    "lead",
    "large",
    "high",
)
IMAGE_PATH_HINTS = ("/jpg/", "/jpeg/", "/png/", "/webp/", "/avif/")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")
UI_ASSETS_SKIP_PREFIXES = (
    "/icons/",
    "/logos/",
    "/static/",
    "/_assets/",
    "/assets/",
    "/images/icons/",
)
UI_ASSETS_SKIP_TOKENS = (
    "logo",
    "icon",
    "sprite",
    "favicon",
    "avatar",
    "badge",
    "thumbnail",
    "thumb",
    "placeholder",
    "pixel",
    "tracking",
    "promo",
    "banner",
)
UI_ASSETS_SKIP_HOSTS = (
    "gravatar.com",
    "doubleclick.net",
    "googlesyndication.com",
    "adsystem.com",
)
UI_ASSETS_SKIP_EXTENSIONS = (".gif", ".svg")
SIZE_QUERY_KEYS = ("w", "h", "width", "height", "size", "sz")


class ScraperError(Exception):
    """Raised when an article cannot be scraped."""


class ScraperService:
    """Extracts article content via Jina AI Reader (r.jina.ai)."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.jina_api_key

    async def scrape_article(self, url: str) -> ExtractedArticle:
        """Fetch article content, images, and embeds using Jina Reader JSON API."""
        jina_url = f"{JINA_BASE}{url}"
        logger.info("scraping_via_jina", url=url)

        headers: dict[str, str] = {
            "Accept": "application/json",
            "X-Return-Format": "markdown",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=JINA_TIMEOUT) as client:
                response = await client.get(
                    jina_url,
                    headers=headers,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise ScraperError(f"Jina timed out after {JINA_TIMEOUT}s for {url}") from None
        except httpx.HTTPStatusError as exc:
            raise ScraperError(f"Jina HTTP {exc.response.status_code} for {url}") from exc
        except Exception as exc:
            raise ScraperError(f"Jina failed for {url}: {exc}") from exc

        payload = data.get("data") if isinstance(data, dict) else None
        if not payload:
            payload = data

        title = (payload or {}).get("title") or "Untitled"
        text = (payload or {}).get("content") or (payload or {}).get("text") or ""
        raw_text = text.strip()

        if not raw_text or len(raw_text) < MIN_TEXT_CHARS:
            raise ScraperError(f"Jina returned insufficient content for {url}")

        if len(raw_text) > MAX_CHARS:
            text = raw_text[:MAX_CHARS] + "..."
        else:
            text = raw_text

        raw_images = (payload or {}).get("images") or []
        images = self._extract_images(raw_images, raw_text)

        raw_links = (payload or {}).get("links") or {}
        embeds = self._extract_embeds(raw_links, raw_text)

        logger.info(
            "scraping_jina_success",
            url=url,
            chars=len(text),
            images=len(images),
            embeds=len(embeds),
        )
        return ExtractedArticle(
            title=title,
            text=text,
            images=images,
            embeds=embeds,
        )

    def _extract_images(self, raw_images: list[object], text: str) -> list[str]:
        candidates: list[tuple[str, str, int | None, int | None]] = []
        for item in raw_images:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url:
                    alt = item.get("alt") if isinstance(item.get("alt"), str) else ""
                    width = self._coerce_int(item.get("width"))
                    height = self._coerce_int(item.get("height"))
                    candidates.append((url, alt, width, height))
            elif isinstance(item, str) and item:
                candidates.append((item, "", None, None))

        for url in self._extract_image_urls_from_text(text):
            candidates.append((url, "", None, None))

        scored: list[tuple[int, int, str]] = []
        for idx, (url, alt, width, height) in enumerate(candidates):
            if not self._is_valid_url(url):
                continue
            score = self._score_image_url(url, alt, width, height)
            scored.append((score, idx, url))

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = self._select_scored_urls(scored, min_score=MIN_IMAGE_SCORE)
        if not selected:
            selected = self._select_scored_urls(scored, min_score=-100)
        return selected

    def _extract_embeds(self, raw_links: dict[str, str], text: str) -> list[str]:
        link_urls = [url for url in raw_links.values() if isinstance(url, str)]
        link_urls.extend(self._extract_urls_from_text(text))
        embeds: list[str] = []
        for url in link_urls:
            embed_url = self._to_embed_url(url)
            if embed_url:
                embeds.append(embed_url)
                if len(embeds) >= MAX_EMBEDS:
                    break
        return self._dedupe_keep_order(embeds)

    @staticmethod
    def _extract_image_urls_from_text(text: str) -> list[str]:
        markdown_images = re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)
        html_images = re.findall(r"<img[^>]+src=['\"](https?://[^'\">\s]+)", text, re.IGNORECASE)
        return markdown_images + html_images

    @staticmethod
    def _extract_urls_from_text(text: str) -> list[str]:
        return re.findall(r"https?://[^\s)\]}>\"']+", text)

    @staticmethod
    def _dedupe_keep_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            result = urlparse(url)
            return result.scheme in ("http", "https") and bool(result.netloc)
        except Exception:
            return False

    def _to_embed_url(self, url: str) -> str | None:
        if not self._is_valid_url(url):
            return None

        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if not any(host == domain or host.endswith(f".{domain}") for domain in EMBED_DOMAINS):
            return None

        if "youtube.com" in host:
            if parsed.path.startswith("/embed/"):
                return url
            query = parse_qs(parsed.query)
            video_id = query.get("v", [""])[0]
            if not video_id and parsed.path.startswith("/shorts/"):
                video_id = parsed.path.split("/shorts/")[-1].split("/")[0]
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}"
            return None

        if "youtu.be" in host:
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://www.youtube.com/embed/{video_id}" if video_id else None

        if "vimeo.com" in host:
            if "player.vimeo.com" in host and parsed.path.startswith("/video/"):
                return url
            match = re.search(r"/(\d+)", parsed.path)
            if match:
                return f"https://player.vimeo.com/video/{match.group(1)}"
            return None

        if "twitter.com" in host or "x.com" in host:
            if "/status/" in parsed.path:
                return f"https://twitframe.com/show?url={quote(url, safe='')}"
            return None

        return None

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _select_scored_urls(self, scored: list[tuple[int, int, str]], min_score: int) -> list[str]:
        selected: list[str] = []
        seen: set[str] = set()
        for score, _, url in scored:
            if score < min_score:
                continue
            if url in seen:
                continue
            seen.add(url)
            selected.append(url)
            if len(selected) >= MAX_IMAGES:
                break
        return selected

    def _score_image_url(self, url: str, alt: str, width: int | None, height: int | None) -> int:
        score = 0
        lower_url = url.lower()
        parsed = urlparse(url)
        path = parsed.path.lower()
        host = parsed.netloc.lower()

        if any(token in path for token in IMAGE_HINT_TOKENS):
            score += 2
        if any(ext in path for ext in IMAGE_PATH_HINTS):
            score += 1
        if any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
            score += 1
        if "sortd-service/imaginary" in lower_url:
            score += 2
        if "cloudfront.net" in host:
            score += 1

        if alt:
            alt_lower = alt.lower()
            if not any(token in alt_lower for token in UI_ASSETS_SKIP_TOKENS):
                score += 1
            if any(token in alt_lower for token in IMAGE_HINT_TOKENS):
                score += 1

        if host in UI_ASSETS_SKIP_HOSTS:
            score -= 3
        if any(path.startswith(prefix) for prefix in UI_ASSETS_SKIP_PREFIXES):
            score -= 2
        if any(token in path for token in UI_ASSETS_SKIP_TOKENS):
            score -= 2
        if any(lower_url.endswith(ext) for ext in UI_ASSETS_SKIP_EXTENSIONS):
            score -= 3

        if width and height:
            if width <= 80 or height <= 80:
                score -= 2
            elif width >= 400 or height >= 400:
                score += 1

        query = parse_qs(parsed.query)
        for key in SIZE_QUERY_KEYS:
            if key not in query:
                continue
            for value in query.get(key, []):
                try:
                    size_value = int(value)
                except (TypeError, ValueError):
                    continue
                if size_value <= 64:
                    score -= 3
                elif size_value >= 400:
                    score += 1

        return score

    def _is_probable_asset_image(self, url: str) -> bool:
        lower_url = url.lower()
        parsed = urlparse(url)
        path = parsed.path.lower()
        host = parsed.netloc.lower()

        if host in UI_ASSETS_SKIP_HOSTS:
            return True
        if any(path.startswith(prefix) for prefix in UI_ASSETS_SKIP_PREFIXES):
            return True
        if any(token in path for token in UI_ASSETS_SKIP_TOKENS):
            return True
        if any(lower_url.endswith(ext) for ext in UI_ASSETS_SKIP_EXTENSIONS):
            return True

        query = parse_qs(parsed.query)
        for key in SIZE_QUERY_KEYS:
            if key not in query:
                continue
            for value in query.get(key, []):
                try:
                    if int(value) <= 64:
                        return True
                except (TypeError, ValueError):
                    continue

        return False

