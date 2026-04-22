import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import httpx
from datetime import datetime, timezone

from scrapers.feed_fetcher import fetch_all_feeds, FEED_URLS
from processor.summarizer import run_summarizer
from database import get_session, Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CONFIG_KEY = "feed_generated_at"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S UTC]")


def _get_upstream_generated_at() -> str | None:
    """Fetch feed-x.json and return its generatedAt string."""
    try:
        resp = httpx.get(FEED_URLS["x"], timeout=15, follow_redirects=True)
        resp.raise_for_status()
        return resp.json().get("generatedAt")
    except Exception as e:
        log.warning(f"Could not check generatedAt: {e}")
        return None


def _get_saved_generated_at() -> str | None:
    with get_session() as session:
        row = session.query(Config).filter_by(key=CONFIG_KEY).first()
        return row.value if row else None


def _save_generated_at(value: str):
    with get_session() as session:
        row = session.query(Config).filter_by(key=CONFIG_KEY).first()
        if row:
            row.value = value
        else:
            session.add(Config(key=CONFIG_KEY, value=value))


def run_fetch(force: bool = False):
    print(f"{_ts()} FETCH started")

    upstream = _get_upstream_generated_at()
    if upstream:
        saved = _get_saved_generated_at()
        if upstream == saved:
            print(f"{_ts()} generatedAt unchanged ({upstream}), but fetching anyway to catch any new content.")
        else:
            print(f"{_ts()} Feed updated: {saved} → {upstream}")
    else:
        print(f"{_ts()} Could not read generatedAt, proceeding anyway.")

    feed_results = fetch_all_feeds()
    print(
        f"{_ts()} FETCH completed — "
        f"x:{feed_results['x']} podcast:{feed_results['podcast']} blog:{feed_results['blog']} new records"
    )

    print(f"{_ts()} SUMMARIZE started")
    summary_results = run_summarizer()
    print(
        f"{_ts()} SUMMARIZE completed — "
        f"processed:{summary_results.get('processed',0)} "
        f"failed:{summary_results.get('failed',0)}"
    )

    if upstream:
        _save_generated_at(upstream)

    print(f"{_ts()} ALL DONE")
    return {"feed": feed_results, "summary": summary_results}


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    run_fetch(force=force)
