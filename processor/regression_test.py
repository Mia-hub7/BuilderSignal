"""
回归测试工具 (Regression Test)
用途：
  1. --export    离线导出（不调 LLM）：从 DB 读取已有数据，生成供人工打标的 CSV
  2. 默认模式    回归验证（调 LLM）：重新跑当前 Prompt，与 golden_set.json 对比 PASS/FAIL
  3. --id 36     只验证指定 ID

工作流：
  Step 1  python processor/regression_test.py --export
          → 生成 labeling_YYYYMMDD.csv，含原文链接 + 内容 + 现有分类 + 中文摘要
          → 在 expected 列填入正确分类，note 列写备注，发给 Claude

  Step 2  Claude 读取 CSV → 更新 golden_set.json

  Step 3  python processor/regression_test.py
          → 重新调豆包，对比 golden set，输出 PASS/FAIL 报告

Golden Set 格式（processor/golden_set.json）：
  [{"id": 36, "expected": "行业预判", "note": "LLM认知演变观点"}, ...]

输出文件：
  output/labeling_YYYYMMDD_HHMMSS.csv      — 打标用（--export 模式）
  output/regression_YYYYMMDD_HHMMSS.csv    — 回归结果（默认模式）
  output/regression_YYYYMMDD_HHMMSS.html   — 带颜色的 HTML 报告（默认模式）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import csv
import argparse
import httpx
from datetime import datetime
from openai import OpenAI
from database import get_session, RawContent, Builder, Summary
import config

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    http_client=httpx.Client(trust_env=False),
)

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def load_golden_set() -> dict:
    """Load golden set as {id: {expected, note}}."""
    if not os.path.exists(GOLDEN_SET_PATH):
        return {}
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {item["id"]: item for item in data}


def get_samples(n=None, ids=None) -> list:
    samples = []
    with get_session() as session:
        q = session.query(RawContent).filter(RawContent.raw_text != None)
        if ids:
            q = q.filter(RawContent.id.in_(ids))
        q = q.order_by(RawContent.id.desc())
        if n:
            q = q.limit(n)
        records = q.all()
        for r in records:
            builder_name, builder_bio = "Unknown", ""
            if r.builder_id:
                b = session.query(Builder).filter_by(id=r.builder_id).first()
                if b:
                    builder_name = b.name
                    builder_bio = b.bio or ""
            samples.append({
                "id": r.id,
                "builder_name": builder_name,
                "builder_bio": builder_bio,
                "source": r.source,
                "raw_text": r.raw_text or "",
            })
    return samples


def classify(sample: dict) -> str:
    """Run current production prompt and return category."""
    from processor.claude_client import call_llm
    result = call_llm(
        sample["builder_name"],
        sample["source"],
        sample["raw_text"],
        sample["builder_bio"],
    )
    return result.get("category", "off_topic" if result.get("skip") else "")


def save_csv(results: list, filepath: str):
    """Save results to CSV file."""
    fieldnames = ["ID", "Builder", "来源", "内容预览（前150字）", "AI预测分类", "期望分类", "状态", "备注"]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "ID": r["id"],
                "Builder": r["builder_name"],
                "来源": r["source"],
                "内容预览（前150字）": r["raw_text"][:150].replace("\n", " ").strip(),
                "AI预测分类": r["predicted"],
                "期望分类": r["expected"] or "—",
                "状态": r["status"],
                "备注": r["note"],
            })


def save_html(results: list, filepath: str, summary: dict):
    """Save results to styled HTML file."""
    STATUS_COLOR = {
        "✅ PASS":   "#d4edda",
        "❌ FAIL":   "#f8d7da",
        "⬜ 未打标": "#fff3cd",
    }
    CATEGORY_COLOR = {
        "技术洞察": "#cce5ff",
        "产品动态": "#d4edda",
        "行业预判": "#fff3cd",
        "工具推荐": "#e2d9f3",
        "off_topic": "#e2e3e5",
        "":          "#ffffff",
    }

    rows_html = ""
    for r in results:
        bg = STATUS_COLOR.get(r["status"], "#ffffff")
        cat_bg = CATEGORY_COLOR.get(r["predicted"], "#ffffff")
        exp_bg = CATEGORY_COLOR.get(r["expected"] or "", "#ffffff")
        content_preview = r["raw_text"][:150].replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ").strip()
        rows_html += f"""
        <tr style="background:{bg}">
          <td style="text-align:center">{r['id']}</td>
          <td>{r['builder_name']}</td>
          <td style="text-align:center">{r['source']}</td>
          <td style="font-size:12px;color:#555">{content_preview}…</td>
          <td style="background:{cat_bg};text-align:center;font-weight:bold">{r['predicted']}</td>
          <td style="background:{exp_bg};text-align:center">{r['expected'] or '—'}</td>
          <td style="text-align:center">{r['status']}</td>
          <td style="font-size:12px;color:#555">{r['note']}</td>
        </tr>"""

    acc_line = ""
    if summary["labeled"] > 0:
        acc = summary["passed"] / summary["labeled"] * 100
        color = "#28a745" if acc >= 90 else "#ffc107" if acc >= 70 else "#dc3545"
        acc_line = f'<span style="color:{color};font-weight:bold">准确率 {acc:.0f}% ({summary["passed"]}/{summary["labeled"]})</span>'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <title>BuilderSignal 回归测试结果</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #212529; }}
    h1 {{ font-size: 20px; margin-bottom: 4px; }}
    .meta {{ color: #6c757d; font-size: 13px; margin-bottom: 20px; }}
    .summary {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px;
                padding: 12px 20px; margin-bottom: 24px; font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th {{ background: #343a40; color: #fff; padding: 10px 12px; text-align: left; white-space: nowrap; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #dee2e6; vertical-align: top; }}
    tr:hover td {{ filter: brightness(0.96); }}
    .legend {{ margin-top: 16px; font-size: 12px; color: #6c757d; }}
    .dot {{ display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:4px; vertical-align:middle; }}
  </style>
</head>
<body>
  <h1>BuilderSignal 回归测试结果</h1>
  <div class="meta">生成时间：{summary['timestamp']}　|　共 {summary['total']} 条　|　已打标 {summary['labeled']} 条　|　{acc_line}</div>
  <div class="summary">
    ✅ PASS {summary['passed']} 条　　❌ FAIL {summary['failed']} 条　　⬜ 未打标 {summary['unlabeled']} 条
  </div>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Builder</th><th>来源</th><th>内容预览（前150字）</th>
        <th>AI预测分类</th><th>期望分类</th><th>状态</th><th>备注</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <div class="legend">
    颜色说明：
    <span class="dot" style="background:#d4edda"></span>PASS / 产品动态
    <span class="dot" style="background:#f8d7da"></span>FAIL
    <span class="dot" style="background:#fff3cd"></span>未打标 / 行业预判
    <span class="dot" style="background:#cce5ff"></span>技术洞察
    <span class="dot" style="background:#e2d9f3"></span>工具推荐
    <span class="dot" style="background:#e2e3e5"></span>off_topic
  </div>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


def run(args):
    golden = load_golden_set()
    ids = [int(x) for x in args.id.split(",")] if args.id else None
    samples = get_samples(ids=ids)

    print(f"\n{'='*80}")
    print(f"回归测试  共 {len(samples)} 条  Golden Set {len(golden)} 条")
    print(f"{'='*80}\n")

    results = []
    for s in samples:
        predicted = classify(s)
        gold = golden.get(s["id"])
        expected = gold["expected"] if gold else None
        note = gold["note"] if gold else ""

        if expected is None:
            status = "⬜ 未打标"
        elif predicted == expected:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        results.append({**s, "predicted": predicted, "expected": expected,
                        "status": status, "note": note})

        print(f"[{s['id']}] {s['builder_name']} ({s['source']})  {status}")
        print(f"  内容: {s['raw_text'][:120].strip()}...")
        print(f"  预测: {predicted}  |  期望: {expected or '—'}  {('| ' + note) if note else ''}")
        print()

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    labeled   = [r for r in results if r["expected"] is not None]
    passed    = [r for r in labeled if r["status"] == "✅ PASS"]
    failed    = [r for r in labeled if r["status"] == "❌ FAIL"]
    unlabeled = [r for r in results if r["expected"] is None]

    print(f"{'='*80}")
    print(f"汇总：{len(samples)} 条样本 | 已打标 {len(labeled)} 条 | "
          f"PASS {len(passed)} | FAIL {len(failed)}")
    if labeled:
        acc = len(passed) / len(labeled) * 100
        print(f"准确率: {acc:.0f}%  ({len(passed)}/{len(labeled)})")

    if failed:
        print(f"\n❌ Bad Cases（需分析原因并迭代 Prompt）：")
        for r in failed:
            print(f"  [{r['id']}] {r['builder_name']}: 预测={r['predicted']} 期望={r['expected']}")
            print(f"       内容: {r['raw_text'][:100].strip()}...")
            if r["note"]:
                print(f"       备注: {r['note']}")

    if unlabeled and not args.id:
        print(f"\n⬜ 未打标条目（共 {len(unlabeled)} 条，请在 golden_set.json 补充 expected）：")
        for r in unlabeled:
            print(f"  {{\"id\": {r['id']}, \"expected\": \"{r['predicted']}\", \"note\": \"\"}},  "
                  f"# {r['builder_name']} | {r['raw_text'][:60].strip()}")

    # ── 输出文件 ───────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = os.path.join(OUTPUT_DIR, f"regression_{ts}.csv")
    html_path = os.path.join(OUTPUT_DIR, f"regression_{ts}.html")

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total":     len(results),
        "labeled":   len(labeled),
        "passed":    len(passed),
        "failed":    len(failed),
        "unlabeled": len(unlabeled),
    }

    save_csv(results, csv_path)
    save_html(results, html_path, summary)

    print(f"\n{'='*80}")
    print(f"📄 结果已保存：")
    print(f"   CSV  → {csv_path}")
    print(f"   HTML → {html_path}")
    print(f"{'='*80}")

    return results


def export_for_labeling():
    """离线导出打标用 CSV，不调用 LLM，直接读 DB 现有数据。"""
    rows = []
    with get_session() as session:
        summaries = session.query(Summary).order_by(Summary.raw_content_id).all()
        for s in summaries:
            rc = session.query(RawContent).filter_by(id=s.raw_content_id).first()
            b  = session.query(Builder).filter_by(id=s.builder_id).first()

            raw_text  = (rc.raw_text or "") if rc else ""
            published = rc.published_at.strftime("%Y-%m-%d %H:%M") if rc and rc.published_at else ""
            url       = (rc.url if rc else None) or s.original_url or ""
            name      = b.name if b else "Unknown"
            source    = rc.source if rc else ""

            rows.append({
                "raw_content_id": s.raw_content_id,
                "Builder":        name,
                "来源":           source,
                "发布时间":       published,
                "原文链接":       url,
                "原文内容（前300字）": raw_text[:300].replace("\n", " ").strip(),
                "AI预测分类":     s.category_tag or "",
                "中文摘要":       s.summary_zh or "",
                "expected":       "",
                "note":           "",
            })

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"labeling_{ts}.csv")

    fieldnames = ["raw_content_id", "Builder", "来源", "发布时间", "原文链接",
                  "原文内容（前300字）", "AI预测分类", "中文摘要", "expected", "note"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ 导出完成：{len(rows)} 条记录")
    print(f"   文件路径：{path}")
    print(f"\n下一步：")
    print(f"  1. 打开 CSV，对照原文链接核对每行的 AI预测分类是否正确")
    print(f"  2. 在 expected 列填入正确分类（技术洞察/产品动态/行业预判/工具推荐/off_topic）")
    print(f"  3. note 列写判断依据（可选）")
    print(f"  4. 将填好的 CSV 发给 Claude，更新 golden_set.json 后运行回归验证")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true", help="离线导出打标 CSV，不调用 LLM")
    parser.add_argument("--id", type=str, default="", help="指定 ID，逗号分隔（回归模式用）")
    args = parser.parse_args()

    if args.export:
        export_for_labeling()
    else:
        run(args)
