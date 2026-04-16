import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import logging
from datetime import datetime, timezone

from database import get_session, Builder, RawContent
from scrapers.base_scraper import generate_content_id, is_duplicate
from scrapers.supadata_client import get_youtube_transcript, is_youtube_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FEED_URLS = {
    "x":       "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json",
    "podcast": "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json",
    "blog":    "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json",
}


def _fetch_json(url: str) -> dict | None:
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None


def _parse_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _get_builder_id_by_handle(handle: str, session) -> int | None:
    b = session.query(Builder).filter_by(handle=handle, is_active=1).first()
    return b.id if b else None


def _get_builder_id_by_name(name: str, category: str, session) -> int | None:
    b = session.query(Builder).filter_by(name=name, category=category, is_active=1).first()
    return b.id if b else None


def _process_x(data: dict, session) -> int:
    count = 0
    for builder in data.get("x", []):
        handle = builder.get("handle", "")
        builder_id = _get_builder_id_by_handle(handle, session)
        for tweet in builder.get("tweets", []):
            tweet_id = str(tweet.get("id", ""))
            if not tweet_id:
                continue
            content_id = generate_content_id(tweet_id)
            if is_duplicate(content_id, session):
                continue
            session.add(RawContent(
                builder_id=builder_id,
                source="x",
                content_id=content_id,
                url=tweet.get("url", ""),
                raw_text=tweet.get("text", ""),
                published_at=_parse_datetime(tweet.get("createdAt")),
            ))
            count += 1
    return count


def _process_podcasts(data: dict, session) -> int:
    count = 0
    for pod in data.get("podcasts", []):
        url = pod.get("url", "")
        guid = pod.get("guid", url)
        if not guid:
            continue
        content_id = generate_content_id(guid)
        if is_duplicate(content_id, session):
            continue
        name = pod.get("name", "")
        builder_id = _get_builder_id_by_name(name, "podcast", session)
        title = pod.get("title", "")
        transcript = pod.get("transcript", "")
        # If transcript is missing and URL is YouTube, fetch via Supadata
        if not transcript and is_youtube_url(url):
            log.info(f"Fetching YouTube transcript for: {url}")
            transcript = get_youtube_transcript(url)
        raw_text = f"{title}\n\n{transcript}".strip()
        session.add(RawContent(
            builder_id=builder_id,
            source="podcast",
            content_id=content_id,
            url=url,
            raw_text=raw_text,
            published_at=_parse_datetime(pod.get("publishedAt")),
        ))
        count += 1
    return count


def _process_blogs(data: dict, session) -> int:
    count = 0
    for post in data.get("blogs", []):
        url = post.get("url", "")
        if not url:
            continue
        content_id = generate_content_id(url)
        if is_duplicate(content_id, session):
            continue
        name = post.get("name", "")
        builder_id = _get_builder_id_by_name(name, "blog", session)
        title = post.get("title", "")
        body = post.get("content", post.get("body", ""))
        raw_text = f"{title}\n\n{body}".strip()
        session.add(RawContent(
            builder_id=builder_id,
            source="blog",
            content_id=content_id,
            url=url,
            raw_text=raw_text,
            published_at=_parse_datetime(post.get("publishedAt")),
        ))
        count += 1
    return count


def fetch_all_feeds() -> dict:
    results = {"x": 0, "podcast": 0, "blog": 0}

    with get_session() as session:
        for source, url in FEED_URLS.items():
            log.info(f"Fetching {source} feed...")
            data = _fetch_json(url)
            if data is None:
                log.error(f"Skipping {source} feed due to fetch error.")
                continue
            if source == "x":
                results["x"] = _process_x(data, session)
            elif source == "podcast":
                results["podcast"] = _process_podcasts(data, session)
            elif source == "blog":
                results["blog"] = _process_blogs(data, session)
            log.info(f"{source} feed: {results[source]} new records inserted.")

    return results


if __name__ == "__main__":
    totals = fetch_all_feeds()
    print(f"Done — x:{totals['x']} podcast:{totals['podcast']} blog:{totals['blog']}")
