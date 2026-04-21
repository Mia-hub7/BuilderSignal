"""
导出摘要质量评分样本
运行：python scripts/export_eval_samples.py
输出：output/eval_samples.md（15条，覆盖不同 builder / source / category）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from database import get_session, Summary, Builder, RawContent

SAMPLE_SIZE = 15
OUTPUT_PATH = "output/eval_samples.md"

def main():
    os.makedirs("output", exist_ok=True)
    with get_session() as session:
        all_rows = (
            session.query(Summary)
            .filter(Summary.is_visible == 1)
            .all()
        )

        # 拉取 source 信息
        def get_source(sm):
            if sm.raw_content_id:
                rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
                if rc:
                    return rc.source
            return "unknown"

        for sm in all_rows:
            sm._source = get_source(sm)

        # 分层抽样：按 source × category 分6个桶，目标分配：
        #   x-深度(4) x-观点(5) podcast-深度(2) podcast-观点(1) blog-深度(2) blog-观点(1)
        buckets = {
            ("x",       "深度内容"): 5,
            ("x",       "观点速览"): 6,
            ("podcast", "深度内容"): 2,
            ("blog",    "深度内容"): 2,
        }

        random.seed(42)
        sample = []
        for (src, cat), n in buckets.items():
            pool = [s for s in all_rows if s._source == src and s.category_tag == cat]
            picked = random.sample(pool, min(n, len(pool)))
            sample += picked
            print(f"  {src} · {cat}：目标{n}条，实际抽{len(picked)}条（库中{len(pool)}条）")

        random.shuffle(sample)

        lines = []
        lines.append("# 摘要质量评分样本\n")
        lines.append("**评分标准（每条满分15分）：**\n")
        lines.append("- **A 信息提炼度**（1-5分）：摘要是否提炼出了核心观点？有没有废话套话？")
        lines.append('- **B Builder视角**（1-5分）：是否保留了第一人称语气？有没有变成"XX认为/指出"？')
        lines.append("- **C 可读性**（1-5分）：中文是否地道流畅？有没有翻译腔？\n")
        lines.append("---\n")

        for i, sm in enumerate(sample, 1):
            builder_name = "Unknown"
            source = "unknown"
            if sm.builder_id:
                b = session.query(Builder).filter_by(id=sm.builder_id).first()
                if b:
                    builder_name = b.name
            if sm.raw_content_id:
                rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
                if rc:
                    source = rc.source

            lines.append(f"## 第{i}条　`id={sm.id}` · {builder_name} · {source} · {sm.category_tag}")

            # 原始内容
            raw_text = ""
            if sm.raw_content_id:
                rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
                if rc and rc.raw_text:
                    raw_text = rc.raw_text.strip()

            lines.append(f"\n**原文（前300字）：**\n```\n{raw_text or '（无）'}\n```\n")
            lines.append(f"**中文摘要：**\n> {(sm.summary_zh or '').strip()}\n")
            lines.append(f"**英文摘要：**\n> {(sm.summary_en or '').strip()}\n")

            lines.append("**我的评分：** A=__ / B=__ / C=__　总分=__ / 15\n")
            lines.append("**备注：**（可选，记录具体问题）\n")
            lines.append("---\n")

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    print(f"已导出 {len(sample)} 条样本 → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
