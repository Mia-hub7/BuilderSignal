"""
数据库诊断脚本：检查旧标签分布和 published_at 空值情况
运行方式：python scripts/db_inspect.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session, Summary, RawContent
from sqlalchemy import func

NEW_CATEGORIES = {"深度内容", "观点速览"}
OLD_CATEGORIES = {"技术洞察", "产品动态", "行业预判", "工具推荐"}

with get_session() as session:
    # ── 1. category_tag 分布 ──────────────────────────────────────────────────
    print("=" * 55)
    print("【1】summaries.category_tag 分布（is_visible=1）")
    print("=" * 55)
    rows = (
        session.query(Summary.category_tag, func.count(Summary.id))
        .filter(Summary.is_visible == 1)
        .group_by(Summary.category_tag)
        .order_by(func.count(Summary.id).desc())
        .all()
    )
    total = 0
    old_count = 0
    new_count = 0
    for tag, cnt in rows:
        flag = ""
        if tag in OLD_CATEGORIES:
            flag = "  ← 旧标签"
            old_count += cnt
        elif tag in NEW_CATEGORIES:
            flag = "  ← 新标签"
            new_count += cnt
        else:
            flag = "  ← 其他/空"
        print(f"  {str(tag):<12}  {cnt:>4} 条{flag}")
        total += cnt
    print(f"\n  合计：{total} 条 | 旧标签：{old_count} 条 | 新标签：{new_count} 条")

    # ── 2. published_at 空值统计 ──────────────────────────────────────────────
    print()
    print("=" * 55)
    print("【2】summaries.published_at 空值统计（is_visible=1）")
    print("=" * 55)
    total_visible = session.query(Summary).filter(Summary.is_visible == 1).count()
    null_pub = (
        session.query(Summary)
        .filter(Summary.is_visible == 1, Summary.published_at == None)
        .count()
    )
    print(f"  总可见条数：{total_visible}")
    print(f"  published_at 为 NULL：{null_pub} 条 ({null_pub/total_visible*100:.1f}%)")

    # ── 3. published_at 空值按来源分布 ──────────────────────────────────────
    print()
    print("=" * 55)
    print("【3】published_at 空值 — 按 source 分布")
    print("=" * 55)
    null_rows = (
        session.query(Summary)
        .filter(Summary.is_visible == 1, Summary.published_at == None)
        .all()
    )
    from collections import Counter
    source_counter = Counter()
    for sm in null_rows:
        src = "unknown"
        if sm.raw_content_id:
            rc = session.query(RawContent).filter_by(id=sm.raw_content_id).first()
            if rc:
                src = rc.source or "unknown"
        source_counter[src] += 1
    if source_counter:
        for src, cnt in source_counter.most_common():
            print(f"  {src:<12}  {cnt:>4} 条")
    else:
        print("  无空值记录")

    # ── 4. 抽样：旧标签数据样例 ───────────────────────────────────────────────
    print()
    print("=" * 55)
    print("【4】旧标签数据样例（最近5条）")
    print("=" * 55)
    old_samples = (
        session.query(Summary)
        .filter(Summary.is_visible == 1, Summary.category_tag.in_(OLD_CATEGORIES))
        .order_by(Summary.created_at.desc())
        .limit(5)
        .all()
    )
    for sm in old_samples:
        print(f"  id={sm.id}  tag={sm.category_tag}  created={sm.created_at}  pub={sm.published_at}")
        print(f"    zh: {(sm.summary_zh or '')[:60]}...")
