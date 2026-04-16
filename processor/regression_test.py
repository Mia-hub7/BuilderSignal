"""
回归测试工具 (Regression Test)
用途：
  1. 首次运行：对全量数据跑当前 Prompt，输出结果供人工打标（label）
  2. 后续运行：与 Golden Set 对比，输出 pass/fail，检验准确率和有无回归

运行方式：
  python processor/regression_test.py            # 全量扫描 + 对比 Golden Set
  python processor/regression_test.py --scan     # 只扫描，不对比（用于初次打标）
  python processor/regression_test.py --id 36    # 只跑指定 ID

Golden Set 格式（processor/golden_set.json）：
  [{"id": 36, "expected": "行业预判", "note": "LLM认知演变观点"}, ...]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
import httpx
from openai import OpenAI
from database import get_session, RawContent, Builder
import config

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    http_client=httpx.Client(trust_env=False),
)

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set.json")


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
    return result.get("category", "")


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
    labeled = [r for r in results if r["expected"] is not None]
    passed  = [r for r in labeled if r["status"] == "✅ PASS"]
    failed  = [r for r in labeled if r["status"] == "❌ FAIL"]

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

    # ── 输出未打标条目（供首次打标用）──────────────────────────────────────
    unlabeled = [r for r in results if r["expected"] is None]
    if unlabeled and not args.id:
        print(f"\n⬜ 未打标条目（共 {len(unlabeled)} 条，请在 golden_set.json 补充 expected）：")
        for r in unlabeled:
            print(f"  {{\"id\": {r['id']}, \"expected\": \"{r['predicted']}\", \"note\": \"\"}},  "
                  f"# {r['builder_name']} | {r['raw_text'][:60].strip()}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="只扫描不对比")
    parser.add_argument("--id", type=str, default="", help="指定 ID，逗号分隔")
    args = parser.parse_args()
    run(args)
