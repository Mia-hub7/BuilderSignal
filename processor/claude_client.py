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

SYSTEM_PROMPT = """你是一个专业的 AI 行业内容分析师。
你的任务是对 AI Builder 发布的内容进行分类和摘要。
你必须只返回合法的 JSON，不要包含任何 Markdown 代码块或额外说明。"""

USER_PROMPT_TEMPLATE = """以下是 {builder_name} 在 {source} 上发布的内容：

{raw_text}

请完成以下任务：
对内容进行分类，并生成双语摘要，返回以下 JSON：
{{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}}

只返回 JSON，不要包含任何其他内容。"""


def call_llm(builder_name: str, source: str, raw_text: str) -> dict:
    """Call LLM API to analyze and summarize content.

    Returns a dict with keys: skip, category, summary_zh, summary_en.
    On skip, returns {"skip": True}.
    Raises on API error.
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(
        builder_name=builder_name,
        source=source,
        raw_text=raw_text[:4000],
    )

    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    result = json.loads(raw)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = (
        "We just shipped a new version of Claude that can use a computer just like you do "
        "- browsing the web, writing and executing code, and more. "
        "This is a significant step towards more autonomous AI systems."
    )
    print("Calling LLM with sample content...")
    result = call_llm("Anthropic", "x", sample)
    print("Result:", json.dumps(result, ensure_ascii=False, indent=2))

    print("\nCalling again to verify API works consistently...")
    result2 = call_llm("Andrej Karpathy", "x", "Just had breakfast. Eggs were great.")
    print("Result (should skip):", json.dumps(result2, ensure_ascii=False, indent=2))
