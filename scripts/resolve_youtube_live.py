"""Resolve YouTube live embed metadata for a channel URL.

Usage:
  python scripts/resolve_youtube_live.py https://www.youtube.com/@aljazeeraenglish
"""

from __future__ import annotations

import json
import sys

import yt_dlp


def get_embed_data(channel_url: str) -> dict[str, str | bool | None]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"{channel_url.rstrip('/')}/live", download=False)
            return {
                "id": info.get("id"),
                "can_embed": info.get("allow_embed", True),
                "title": info.get("title"),
            }
        except Exception as exc:
            return {"error": str(exc)}


def main() -> int:
    if len(sys.argv) < 2:
        print("Provide a YouTube channel URL.")
        return 1

    data = get_embed_data(sys.argv[1])
    print(json.dumps(data, indent=2))

    if data.get("id") and data.get("can_embed"):
        print(f"Embed URL: https://www.youtube.com/embed/{data['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
