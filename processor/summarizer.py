import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from database import get_session, RawContent, Summary, Builder
from processor.claude_client import call_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BATCH_SIZE = 20


def run_summarizer() -> dict:
    processed = skipped = failed = 0

    with get_session() as session:
        pending = (
            session.query(RawContent)
            .filter_by(is_processed=0)
            .limit(BATCH_SIZE)
            .all()
        )

        log.info(f"Found {len(pending)} unprocessed records.")

        for record in pending:
            builder_name = "Unknown"
            if record.builder_id:
                builder = session.query(Builder).filter_by(id=record.builder_id).first()
                if builder:
                    builder_name = builder.name

            try:
                result = call_llm(builder_name, record.source, record.raw_text or "")
            except Exception as e:
                log.error(f"LLM call failed for raw_content id={record.id}: {e}")
                failed += 1
                continue

            if result.get("skip"):
                record.is_processed = 2
                skipped += 1
                log.info(f"Skipped id={record.id} ({builder_name})")
            else:
                session.add(Summary(
                    raw_content_id=record.id,
                    builder_id=record.builder_id,
                    category_tag=result.get("category", ""),
                    summary_zh=result.get("summary_zh", ""),
                    summary_en=result.get("summary_en", ""),
                    original_url=record.url,
                    published_at=record.published_at,
                ))
                record.is_processed = 1
                processed += 1
                log.info(f"Summarized id={record.id} ({builder_name}) → {result.get('category')}")

    log.info(f"Done — processed:{processed} skipped:{skipped} failed:{failed}")
    return {"processed": processed, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    totals = run_summarizer()
    print(f"Result: {totals}")
