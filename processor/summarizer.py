import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import logging
from database import get_session, RawContent, Summary, Builder
from processor.claude_client import classify, summarize, translate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BATCH_SIZE = 100
SHORT_TEXT_THRESHOLD = 30  # 去除 URL 后低于此字符数 → 直接存原文，不调 summarize


def _text_without_urls(raw_text: str) -> str:
    return re.sub(r'https?://\S+', '', raw_text or '').strip()


def run_summarizer() -> dict:
    processed = failed = 0

    with get_session() as session:
        pending_ids = [
            r.id for r in session.query(RawContent.id)
            .filter_by(is_processed=0)
            .limit(BATCH_SIZE)
            .all()
        ]

    log.info(f"Found {len(pending_ids)} unprocessed records.")

    for record_id in pending_ids:
        with get_session() as session:
            record = session.query(RawContent).filter_by(id=record_id).first()
            if not record or record.is_processed:
                continue
            builder_name = "Unknown"
            builder_bio = ""
            if record.builder_id:
                builder = session.query(Builder).filter_by(id=record.builder_id).first()
                if builder:
                    builder_name = builder.name
                    builder_bio = builder.bio or ""
            raw_text = record.raw_text or ""
            source = record.source
            builder_id = record.builder_id
            url = record.url
            published_at = record.published_at

        try:
            category = classify(builder_name, source, raw_text, builder_bio)

            # 短内容：英文原文 + 翻译成中文，不调 summarize 避免 LLM 扩充编造
            if len(_text_without_urls(raw_text)) < SHORT_TEXT_THRESHOLD:
                summary_en = raw_text
                summary_zh = translate(raw_text)
                log.info(f"Short content id={record_id} ({builder_name}) → 翻译原文, category={category}")
            else:
                result = summarize(builder_name, source, raw_text, category, builder_bio)
                summary_zh = result.get("summary_zh", "")
                summary_en = result.get("summary_en", "")

        except Exception as e:
            log.error(f"LLM call failed for raw_content id={record_id}: {e}")
            failed += 1
            continue

        with get_session() as session:
            record = session.query(RawContent).filter_by(id=record_id).first()
            if record:
                session.add(Summary(
                    raw_content_id=record.id,
                    builder_id=builder_id,
                    category_tag=category,
                    summary_zh=summary_zh,
                    summary_en=summary_en,
                    original_url=url,
                    published_at=published_at,
                ))
                record.is_processed = 1
                processed += 1
                log.info(f"Processed id={record_id} ({builder_name}) → {category}")

    log.info(f"Done — processed:{processed} failed:{failed}")
    return {"processed": processed, "failed": failed}


if __name__ == "__main__":
    totals = run_summarizer()
    print(f"Result: {totals}")
