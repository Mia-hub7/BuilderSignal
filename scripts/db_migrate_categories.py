"""
数据迁移：旧四类标签 → 新两类标签，并用 created_at 回填 published_at 空值

映射规则：
  技术洞察 / 产品动态 / 工具推荐 → 深度内容
  行业预判                        → 观点速览

published_at 空值：用 created_at 回填（blog 来源无发布时间时的兜底）

运行方式：python scripts/db_migrate_categories.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session, Summary

CATEGORY_MAP = {
    "技术洞察": "深度内容",
    "产品动态": "深度内容",
    "工具推荐": "深度内容",
    "行业预判": "观点速览",
}

with get_session() as session:
    # ── 1. 迁移旧标签 ──────────────────────────────────────────────────────────
    tag_updated = 0
    for old_tag, new_tag in CATEGORY_MAP.items():
        rows = session.query(Summary).filter(Summary.category_tag == old_tag).all()
        for sm in rows:
            sm.category_tag = new_tag
            tag_updated += 1
    print(f"category_tag 迁移：{tag_updated} 条")

    # ── 2. 回填 published_at 空值 ──────────────────────────────────────────────
    null_rows = session.query(Summary).filter(Summary.published_at == None).all()
    pub_filled = 0
    for sm in null_rows:
        if sm.created_at:
            sm.published_at = sm.created_at
            pub_filled += 1
    print(f"published_at 回填：{pub_filled} 条（使用 created_at）")

print("完成。")
