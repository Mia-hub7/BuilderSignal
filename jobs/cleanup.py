import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from database import get_session, Summary, RawContent


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S UTC]")


def run_cleanup(days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        deleted_sm = (
            session.query(Summary)
            .filter(Summary.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        deleted_rc = (
            session.query(RawContent)
            .filter(RawContent.fetched_at < cutoff)
            .delete(synchronize_session=False)
        )

    print(f"{_ts()} CLEANUP: deleted {deleted_sm} summaries, {deleted_rc} raw_content")
    return {"summaries": deleted_sm, "raw_content": deleted_rc}


if __name__ == "__main__":
    run_cleanup()
