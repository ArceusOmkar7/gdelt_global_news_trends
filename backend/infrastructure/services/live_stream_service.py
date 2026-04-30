"""Live stream resolver service for YouTube channels."""

from __future__ import annotations

import threading
import time
from typing import Any

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None  # type: ignore[assignment]

CHANNEL_GROUPS: dict[str, dict[str, Any]] = {
    "GLOBAL": {
        "label": "GLOBAL",
        "channels": [
            {"name": "Al Jazeera English", "id": "UCNye-wNBqNL5ZzHSJj3l8Bg"},
            {"name": "FRANCE 24 English", "id": "UCQfwfsi5VrQ8yKZ-UWmAEFg"},
            {"name": "CNN", "id": "UCupvZG-5ko_eiXAupbDfxWw"},
            {"name": "Sky News", "id": "UCoMdktPbSTixAyNGwb-UYkQ"},
            {"name": "Reuters", "id": "UChqUTb7kYRX8-EiaN3XFrSQ"},
        ],
    },
    "US": {
        "label": "UNITED STATES",
        "channels": [
            {"name": "ABC News", "id": "UCBi2mrWuNuyYy4gbM6fU18Q"},
            {"name": "CBS News", "id": "UC8p1vwvWtl6T73JiExfWs1g"},
            {"name": "Fox News", "id": "UCXIJgqnII2ZOINSWNOGFThA"},
            {"name": "NBC News", "id": "UCeY0bbntWzzVIaj2z3QigXg"},
        ],
    },
    "IR": {
        "label": "IRAN",
        "channels": [
            {"name": "Iran International (Persian)", "id": "UCat6bC0Wrqq9Bcq7EkH_yQw"},
            {"name": "IRIB News (Persian)", "id": "UCat6bC0Wrqq9Bcq7EkH_yQw"},
            {"name": "ABC News (English)", "id": "UCBi2mrWuNuyYy4gbM6fU18Q"},
            {"name": "BBC Persian", "id": "UCHZk9MrT3DGWmVqdsj5y0EA"},
        ],
    },
    # "IS": {
    #     "label": "ISRAEL",
    #     "channels": [
    #         {"name": "Kan 11 (Hebrew)", "id": "UC7S2pX9v8YF7N6Yh7sY-yqQ"},
    #         {"name": "N12 News (Hebrew)", "id": "UCYfP3vP7vO-u_tU6f8e7L_w"},
    #         {"name": "i24NEWS English", "id": "UCvHDpsWKADrDia0c99X37vg"},
    #         {"name": "ILTV Israel News (English)", "id": "UCk0c-I4F0_M5n_xX_k-f-UA"},
    #     ],
    # },
    "UK": {
        "label": "UNITED KINGDOM",
        "channels": [
            {"name": "BBC News", "id": "UC16niRr50-MSBwiO3YDb3RA"},
            {"name": "Sky News", "id": "UCoMdktPbSTixAyNGwb-UYkQ"},
            {"name": "GB News", "id": "UC0vn8ISa4LKMunLbzaXLnOQ"},
            {"name": "Channel 4 News", "id": "UCTrQ7HXWRRxr7OsOtodr2_w"},
        ],
    },
    # "RS": {
    #     "label": "RUSSIA",
    #     "channels": [
    #         {"name": "Rossiya 24 (Russian)", "id": "UC_j_vX0X_0x_0x_0x_0x"},
    #         {"name": "NTV (Russian)", "id": "UCLp_0_0_0_0_0_0_0_0"},
    #         {"name": "RT News (English)", "id": "UCpwvZwUam-URkxB7g4USKpg"},
    #         {"name": "RT News (Russian)", "id": "UCpwvZwUam-URkxB7g4USKpg"},
    #     ],
    # },
    "IN": {
        "label": "INDIA",
        "channels": [
            {"name": "Aaj Tak (Hindi)", "id": "UCt4t-jeY85JegMlZ-E5UWtA"},
            {"name": "ABP News (Hindi)", "id": "UCRWFSbif-RFENbBrSiez1DA"},
            {"name": "India Today (English)", "id": "UCYPvAwZP8pZhSMW8qs7cVCw"},
            {"name": "NDTV (English)", "id": "UCZFMm1mMw0F81Z37aaEzTUA"},
        ],
    },
}

DEFAULT_GROUP = "GLOBAL"
CACHE_TTL_SECONDS = 600.0


class LiveStreamService:
    """Resolve and cache live stream video IDs for YouTube channels."""

    def __init__(self) -> None:
        if yt_dlp is None:
            raise RuntimeError("yt-dlp is required for live stream resolution")
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_group(self, country_code: str | None) -> dict[str, Any]:
        group_key = country_code.upper() if country_code else DEFAULT_GROUP
        if group_key not in CHANNEL_GROUPS:
            group_key = DEFAULT_GROUP
        group = CHANNEL_GROUPS[group_key]
        channels = [self.resolve_channel(ch["id"], ch["name"], force_refresh=False) for ch in group["channels"]]
        return {"group_key": group_key, "label": group["label"], "channels": channels}

    def refresh_channel(self, channel_id: str) -> dict[str, Any]:
        for group in CHANNEL_GROUPS.values():
            for channel in group["channels"]:
                if channel["id"] == channel_id:
                    return self.resolve_channel(channel_id, channel["name"], force_refresh=True)
        return self.resolve_channel(channel_id, channel_id, force_refresh=True)

    def resolve_channel(self, channel_id: str, name: str, force_refresh: bool) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(channel_id)
            if cached and not force_refresh and (now - cached["updated_at"]) < CACHE_TTL_SECONDS:
                return cached

        result = self._fetch_live_info(channel_id, name)
        with self._lock:
            self._cache[channel_id] = result
        return result

    def _fetch_live_info(self, channel_id: str, name: str) -> dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        updated_at = time.monotonic()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/channel/{channel_id}/live",
                    download=False,
                )
            video_id = info.get("id")
            can_embed = bool(info.get("allow_embed", True))
            title = info.get("title")
            if not video_id:
                return {
                    "id": channel_id,
                    "name": name,
                    "video_id": None,
                    "embed_url": None,
                    "can_embed": can_embed,
                    "status": "error",
                    "error": "Live stream not found",
                    "title": title,
                    "updated_at": updated_at,
                }
            if not can_embed:
                return {
                    "id": channel_id,
                    "name": name,
                    "video_id": video_id,
                    "embed_url": None,
                    "can_embed": False,
                    "status": "error",
                    "error": "Embedding disabled",
                    "title": title,
                    "updated_at": updated_at,
                }
            return {
                "id": channel_id,
                "name": name,
                "video_id": video_id,
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
                "can_embed": True,
                "status": "ok",
                "error": None,
                "title": title,
                "updated_at": updated_at,
            }
        except Exception as exc:
            return {
                "id": channel_id,
                "name": name,
                "video_id": None,
                "embed_url": None,
                "can_embed": True,
                "status": "error",
                "error": str(exc),
                "title": None,
                "updated_at": updated_at,
            }


live_stream_service = LiveStreamService()
