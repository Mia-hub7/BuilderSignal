import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timezone

from scrapers.feed_fetcher import fetch_all_feeds
from processor.summarizer import run_summarizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S UTC]")


def run_fetch():
    print(f"{_ts()} FETCH started")
    feed_results = fetch_all_feeds()
    print(
        f"{_ts()} FETCH completed — "
        f"x:{feed_results['x']} podcast:{feed_results['podcast']} blog:{feed_results['blog']} new records"
    )

    print(f"{_ts()} SUMMARIZE started")
    summary_results = run_summarizer()
    print(
        f"{_ts()} SUMMARIZE completed — "
        f"processed:{summary_results['processed']} "
        f"skipped:{summary_results['skipped']} "
        f"failed:{summary_results['failed']}"
    )

    print(f"{_ts()} ALL DONE")
    return {"feed": feed_results, "summary": summary_results}


if __name__ == "__main__":
    run_fetch()
