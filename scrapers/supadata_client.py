import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import httpx
import config

log = logging.getLogger(__name__)

SUPADATA_BASE = "https://api.supadata.ai/v1"


def get_youtube_transcript(url: str) -> str:
    """Fetch transcript for a YouTube video URL via Supadata API.
    Returns transcript text, or empty string on failure.
    """
    if not config.SUPADATA_API_KEY:
        log.warning("SUPADATA_API_KEY not set, skipping transcript fetch.")
        return ""

    try:
        resp = httpx.get(
            f"{SUPADATA_BASE}/youtube/transcript",
            params={"url": url, "text": "true"},
            headers={"x-api-key": config.SUPADATA_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", "")
        if isinstance(content, list):
            return " ".join(item.get("text", "") for item in content)
        return str(content)
    except Exception as e:
        log.error(f"Supadata transcript fetch failed for {url}: {e}")
        return ""


def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url
