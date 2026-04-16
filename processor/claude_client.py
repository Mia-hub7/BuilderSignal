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

SYSTEM_PROMPT = """你是 BuilderSignal 的内容分类与摘要引擎。
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

USER_PROMPT_TEMPLATE = """Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

请对内容进行分类并生成双语摘要，只返回 JSON：
{{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}}"""


def call_llm(builder_name: str, source: str, raw_text: str, builder_bio: str = "") -> dict:
    """Call LLM API to analyze and summarize content.

    Returns a dict with keys: skip, category, summary_zh, summary_en.
    On skip, returns {"skip": True}.
    Raises on API error.
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(
        builder_name=builder_name,
        builder_bio=builder_bio or "",
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
