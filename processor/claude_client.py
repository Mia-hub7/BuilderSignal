import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import httpx
from openai import OpenAI

import config

log = logging.getLogger(__name__)


_client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    http_client=httpx.Client(trust_env=False),
)

# ── 分类标签 Prompt ────────────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """你是 BuilderSignal 的内容分类引擎。
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

CLASSIFY_USER = """Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{{"category": "技术洞察|产品动态|行业预判|工具推荐"}}"""


# ── 摘要 Prompt ────────────────────────────────────────────────────────────────

SUMMARIZE_SYSTEM = """你是 BuilderSignal 的摘要引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

摘要要求：
- 保留 Builder 第一人称视角和语气，不要改写成第三人称描述
- 提炼核心观点，不复述原文，不堆砌套话
- 中英文信息完全一致，不能出现一方有另一方没有的内容
- 长度 2-4 句，宁短勿长，每句有实质内容"""

SUMMARIZE_USER = """Builder: {builder_name}（{builder_bio}）
平台: {source}
分类: {category}
内容:
{raw_text}

只返回 JSON：
{{
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}}"""


# ── 公开接口 ───────────────────────────────────────────────────────────────────

def classify(builder_name: str, source: str, raw_text: str,
             builder_bio: str = "") -> str:
    """Call 1: classify content, return category string."""
    prompt = CLASSIFY_USER.format(
        builder_name=builder_name,
        builder_bio=builder_bio,
        source=source,
        raw_text=raw_text[:4000],
    )
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=32,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content.strip())
    return result.get("category", "")


def summarize(builder_name: str, source: str, raw_text: str,
              category: str, builder_bio: str = "") -> dict:
    """Call 2: generate bilingual summary given the category."""
    prompt = SUMMARIZE_USER.format(
        builder_name=builder_name,
        builder_bio=builder_bio,
        source=source,
        category=category,
        raw_text=raw_text[:4000],
    )
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=512,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content.strip())
    return {
        "summary_zh": result.get("summary_zh", ""),
        "summary_en": result.get("summary_en", ""),
    }


def call_llm(builder_name: str, source: str, raw_text: str,
             builder_bio: str = "") -> dict:
    """Chain classify → summarize, return combined dict.

    Called by summarizer.py. Returns keys: category, summary_zh, summary_en.
    """
    category = classify(builder_name, source, raw_text, builder_bio)
    log.debug(f"classify → {category}")
    summary = summarize(builder_name, source, raw_text, category, builder_bio)
    return {"category": category, **summary}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = (
        "We just shipped a new version of Claude that can use a computer just like you do "
        "- browsing the web, writing and executing code, and more. "
        "This is a significant step towards more autonomous AI systems."
    )
    print("Testing split calls...")
    cat = classify("Anthropic", "x", sample)
    print(f"  classify → {cat}")
    s = summarize("Anthropic", "x", sample, cat)
    print(f"  summarize → {json.dumps(s, ensure_ascii=False, indent=2)}")

    print("\nTesting call_llm wrapper...")
    result = call_llm("Andrej Karpathy", "x",
                      "Fine-tuning is overrated. RAG solves 80% of use cases cheaply.")
    print("  result:", json.dumps(result, ensure_ascii=False, indent=2))
