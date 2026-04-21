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

分类标准（只有两个选项，严格按照唯一判断规则执行）：

- 深度内容：内容包含具体的、可学习或可行动的信息
  包括：技术原理解释、工程实现方案、产品功能发布、工具推荐与使用方法、如何使用某模型/工具的具体技巧
  判断问题：读完这条内容，我能学到一个具体知识或找到一个可以用的东西吗？→ 能，则归此类

- 观点速览：其他所有内容，包括看法、预测、评论、感想、私人动态、纯链接
  判断问题：不属于"深度内容"的 → 一律归此类

排他规则：
- 既有具体信息又有观点 → 优先选"深度内容"
- 拿不准时 → 选观点速览"""

CLASSIFY_USER = """Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{{"category": "深度内容|观点速览"}}"""


# ── 摘要 Prompt ────────────────────────────────────────────────────────────────

SUMMARIZE_SYSTEM = """你是 BuilderSignal 的摘要引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

摘要要求：
- 【最重要】必须用第一人称写作，严禁出现"XX认为"、"XX指出"、"XX表示"、"该作者"等第三人称表述。原文是"I think..."就用"我认为..."，原文是"We built..."就用"我们构建了..."
- 【禁止扩充】原文有多少信息就写多少，严禁推测、脑补或扩展原文未提及的内容
- 提炼核心观点，不复述原文，不堆砌套话
- 中英文信息完全一致，不能出现一方有另一方没有的内容
- 【长度自适应】原文不足 200 字写 2-3 句；原文超过 500 字（播客/博客长文）可写 4-6 句，确保关键信息不遗漏
- 【播客视角】若平台为 podcast，以节目整体核心议题为准，提炼全期最重要的 4-6 个观点，不只采用某位嘉宾的单一视角"""

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


# ── 翻译 Prompt（短内容专用）────────────────────────────────────────────────────

TRANSLATE_SYSTEM = """你是翻译引擎。将用户输入的英文内容翻译成中文。
规则：
- 只翻译，不解释，不扩展，不添加原文没有的信息
- 保留原文语气和标点
- 你必须只返回合法的 JSON，不含任何 Markdown 或额外说明"""

TRANSLATE_USER = """内容：
{raw_text}

只返回 JSON：{{"translation": "中文翻译"}}"""


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
    if isinstance(result, list):
        result = result[0] if result else {}
    return result.get("category", "")


def summarize(builder_name: str, source: str, raw_text: str,
              category: str, builder_bio: str = "") -> dict:
    """Call 2: generate bilingual summary given the category."""
    is_podcast = source == "podcast"
    truncate_limit = 8000 if is_podcast else 4000
    max_tok = 768 if is_podcast else 512
    prompt = SUMMARIZE_USER.format(
        builder_name=builder_name,
        builder_bio=builder_bio,
        source=source,
        category=category,
        raw_text=raw_text[:truncate_limit],
    )
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=max_tok,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content.strip())
    return {
        "summary_zh": result.get("summary_zh", ""),
        "summary_en": result.get("summary_en", ""),
    }


def translate(raw_text: str) -> str:
    """Translate short English content to Chinese. No expansion."""
    prompt = TRANSLATE_USER.format(raw_text=raw_text[:500])
    resp = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": TRANSLATE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=256,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content.strip())
    return result.get("translation", raw_text)


def call_llm(builder_name: str, source: str, raw_text: str,
             builder_bio: str = "") -> dict:
    """Chain classify → summarize, return combined dict.

    Called by summarizer.py.
    Returns keys: category, summary_zh, summary_en.
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
