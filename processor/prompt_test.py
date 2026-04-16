"""
Prompt 调优测试脚本
用途：对比不同 Prompt 版本在真实数据上的分类效果
运行：python processor/prompt_test.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import httpx
from openai import OpenAI
import config

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    http_client=httpx.Client(trust_env=False),
)

# ── 从数据库拉取真实数据 ──────────────────────────────────────────────
def get_test_samples(n=10):
    from database import get_session, RawContent, Builder
    samples = []
    with get_session() as session:
        records = (
            session.query(RawContent)
            .filter(RawContent.raw_text != None)
            .order_by(RawContent.id.desc())
            .limit(n)
            .all()
        )
        for r in records:
            builder_name = "Unknown"
            builder_bio = ""
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
                "raw_text": (r.raw_text or "")[:300],
            })
    return samples


# ── V0.2 基线 Prompt ──────────────────────────────────────────────────
def classify_v02(builder_name, source, raw_text):
    system = """你是一个专业的 AI 行业内容分析师。
你的任务是对 AI Builder 发布的内容进行分类。
你必须只返回合法的 JSON，不要包含任何 Markdown 代码块或额外说明。"""

    user = f"""以下是 {builder_name} 在 {source} 上发布的内容：

{raw_text}

请对内容进行分类，返回以下 JSON：
{{"category": "技术洞察|产品动态|行业预判|工具推荐"}}

只返回 JSON。"""

    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=64,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content.strip())


# ── V1.0 改进 Prompt ──────────────────────────────────────────────────
def classify_v10(builder_name, builder_bio, source, raw_text):
    system = """你是 BuilderSignal 的内容分类引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

分类标准（严格按照定义执行，每条内容只能归属一个类别）：

- 技术洞察：涉及模型原理、工程架构、算法实现、技术路线判断
  判断关键词：训练、推理、架构、参数、fine-tune、RAG、量化、benchmark
  示例：分析 Transformer vs RNN 的取舍、解释为什么选择某种工程方案

- 产品动态：新功能发布、产品上线、版本更新、路线图披露
  判断关键词：launched、shipped、released、上线了、发布、新版本、v2.0
  示例：宣布新产品功能、分享产品更新日志

- 行业预判：对 AI 未来趋势、竞争格局、产业变革的观点与预测
  判断关键词：未来、预测、我认为、趋势、会发生、机会在哪
  示例：预测 Agent 的发展方向、对某技术路线的战略判断

- 工具推荐：Builder 明确提及或推荐的具体工具、库、平台、服务
  判断关键词：推荐、在用、try this、check out、工具名称
  示例：推荐某个开源库、分享自己在用的开发工具

排他规则：
- 既有技术细节又有产品发布 → 优先选"产品动态"
- 既有工具又有技术解释 → 优先选"技术洞察"
- 无法归入以上四类（如日常生活、无实质内容）→ 仍选最接近的一类"""

    user = f"""Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：
{{"category": "技术洞察|产品动态|行业预判|工具推荐"}}"""

    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=64,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content.strip())


# ── 主程序：对比两个版本 ──────────────────────────────────────────────
if __name__ == "__main__":
    print("拉取真实数据...")
    samples = get_test_samples(n=10)
    print(f"共 {len(samples)} 条样本\n")
    print("=" * 80)

    results = []
    for s in samples:
        v02 = classify_v02(s["builder_name"], s["source"], s["raw_text"])
        v10 = classify_v10(s["builder_name"], s["builder_bio"], s["source"], s["raw_text"])

        changed = "⚠️  变化" if v02["category"] != v10["category"] else "✅ 一致"
        results.append({**s, "v02": v02["category"], "v10": v10["category"], "changed": changed})

        print(f"[{s['id']}] {s['builder_name']} ({s['source']})")
        print(f"  内容预览: {s['raw_text'][:80]}...")
        print(f"  V0.2: {v02['category']}")
        print(f"  V1.0: {v10['category']}  {changed}")
        print()

    changed_count = sum(1 for r in results if "变化" in r["changed"])
    print("=" * 80)
    print(f"结果汇总：{len(results)} 条样本，{changed_count} 条分类发生变化")
    print("\n发生变化的条目（需人工判断哪个版本更准确）：")
    for r in results:
        if "变化" in r["changed"]:
            print(f"  [{r['id']}] {r['builder_name']}: V0.2={r['v02']} → V1.0={r['v10']}")
            print(f"       内容: {r['raw_text'][:100]}...")
