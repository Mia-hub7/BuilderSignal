# Prompt Engineering 调优文档: BuilderSignal

| 版本 | 日期 | 作者 |
| :--- | :--- | :--- |
| v1.0 | 2026-04-16 | AI PM |

---

## 一、Prompt 迭代记录

### 1.1 版本演进表

| 版本 | 核心指令 (Short Snippet) | 解决的问题 | 迭代策略 | 效果提升 |
| :--- | :--- | :--- | :--- | :--- |
| V0.1 | `"判断是否值得摘要（skip: true/false），并生成双语摘要"` | 无 | 初始版本，含内容过滤逻辑 | 基线版本 |
| V0.2 | `"对内容进行分类，并生成双语摘要，返回 JSON"` | LLM 误过滤约 30% 白名单内容 | 移除 skip 逻辑，全量入库 | 内容召回率从 70% 提升至 100% |
| V1.0（规划中） | `"Role: AI 行业分析师; Builder: {name}({bio}); 分类标准: 技术洞察=..."` | 分类不一致、摘要复述原文、身份视角缺失 | 角色设定 + Builder 身份注入 + 分类判断标准 + 负面约束 | 预期分类准确率提升 20%+，摘要信息密度提升 |

---

### 1.2 技术攻坚复盘：从"内容过滤"到"全量入库"

**问题背景：**
V0.1 要求 LLM 对每条内容判断是否值得摘要（`skip: true/false`）。上线后发现 37 条白名单内容中有 10-13 条被标记为 skip，Dashboard 只显示约 24 条。

**归因分析：**

| 原因 | 说明 |
| :--- | :--- |
| LLM 偏见 | LLM 倾向跳过简短推文（如"Just shipped X"），而这类内容对追踪者恰恰有信号价值 |
| 判断标准缺失 | Prompt 未定义"值得摘要"的标准，LLM 凭主观判断 |
| 设计逻辑矛盾 | 白名单本身已是人工筛选的信任边界，LLM 二次过滤是重复且不可控的判断层 |

**决策过程：**
- 方案 A：优化过滤 Prompt，给出更明确的"跳过标准" → 风险：仍存在 LLM 偏见，难以量化
- 方案 B：移除过滤逻辑，全量入库 → **选择此方案**
- 核心原则：**Track the Builders, Skip the Influencers** — 白名单即信任，过滤权交还给用户

**结果：** 内容召回率从约 70% 提升至 100%，用户可在 Feed 看到完整当日内容。

---

### 1.3 V1.0 规划 Prompt（待实施）

```
System:
你是 BuilderSignal 的内容分析引擎，专注于提炼顶尖 AI Builder 的一手洞察。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

分类判断标准（必须严格遵守）：
- 技术洞察：涉及模型原理、工程架构、算法实现、技术路线判断
- 产品动态：新功能发布、产品上线、版本更新、路线图披露
- 行业预判：对 AI 未来趋势、竞争格局、产业变革的观点与预测
- 工具推荐：Builder 明确提及或推荐的工具、库、平台、服务

User:
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

请返回以下 JSON：
{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "2-3句。直接陈述 Builder 的核心判断，禁止复述原文，禁止使用'该内容'、'总之'、'不仅如此'等废话开头，要体现 Builder 的身份视角",
  "summary_en": "2-3 sentences. State the builder's key insight directly. No paraphrasing. No filler phrases like 'In this post' or 'The author discusses'."
}
```

---

## 二、Bad Case 归因库

### 2.1 Bad Case 模板说明

每个 Bad Case 记录以下字段：原始输入背景、模型错误输出、错误类型、根因分析、修复方案。

---

### 2.2 Bad Case 记录表

| 案例 ID | 原始输入 (Context) | 模型错误输出 (Bad Output) | 错误类型 | 归因分析 (Root Cause) | 解决方案 (Fix) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| BC-001 | Builder: Josh Woodward (Google Labs VP)<br>内容: "We just launched Gemini 2.0 Flash with native image generation and real-time capabilities..." | category: **技术洞察** | 分类错误 | Prompt 只列出 4 个选项，无判断标准。"launched"含技术词汇，LLM 误判为技术洞察 | V1.0 中加入分类判断标准："产品动态 = 新功能发布/产品上线" |
| BC-002 | Builder: Sam Altman (OpenAI CEO)<br>内容: "The thing that most people don't understand about AGI is that it won't feel like a moment..." | summary_zh: "Sam Altman 表示，大多数人不理解 AGI 的原因是它不会像一个时刻一样到来..." | 摘要复述原文 | Prompt 未明确禁止翻译原文，LLM 倾向于直接翻译而非提炼判断 | V1.0 中加入负面约束："禁止复述原文，直接陈述 Builder 的核心判断" |
| BC-003 | Builder: Garry Tan<br>内容: "We're doubling down on AI-first founders in the next batch..." | summary_zh: "一位创业者表示将加大对 AI 优先创始人的投资..." | 身份视角缺失 | Prompt 只传了 builder_name，未传 bio。LLM 不知道 Garry Tan 是 YC CEO | V1.0 中 User Prompt 加入 `{builder_bio}` 字段 |
| BC-004 | Builder: Andrej Karpathy<br>来源: podcast（4800字转录）<br>raw_text 在第 4000 字处被截断 | summary_zh 内容残缺，末句不完整 | 输入截断导致输出残缺 | `raw_text[:4000]` 硬截断，可能截在句子中间，LLM 收到残缺输入 | 改为按句子边界截断，或对播客内容先做段落摘要再输入 LLM |
| BC-005 | Builder: Swyx<br>内容: "Latent Space pod dropped! We talk to the team behind..." | summary_zh: "一位 AI 从业者分享了播客内容..." | 身份标签模糊 | bio 未传入，LLM 不知道 Swyx 是 Latent Space 联创，摘要用了泛化描述 | 同 BC-003，注入 builder_bio |

---

## 三、质量评估标准（The Rubric）

> 定义什么是"好"——这是 Prompt Engineering 专业性的最高体现。

### 3.1 评分维度（5项，每项1-5分，满分25分）

#### 维度 1：分类准确性（Category Accuracy）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 分类与内容完全匹配，符合分类定义 |
| 4 | 分类合理，存在轻微争议但可接受 |
| 3 | 分类模糊，可归入多个类别 |
| 2 | 分类错误，与内容明显不符 |
| 1 | 完全错误或输出了分类定义之外的值 |

#### 维度 2：信息提炼度（Insight Density）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 直接输出 Builder 的核心判断，不含废话，读完有信息增量 |
| 4 | 包含核心信息，有少量冗余 |
| 3 | 信息量一般，部分是已知常识 |
| 2 | 大量复述原文，几乎没有提炼 |
| 1 | 完全是原文翻译，或内容与原文无关 |

#### 维度 3：Builder 视角准确性（Author Perspective）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 准确体现 Builder 的身份背景和专业视角（如"YC CEO 认为..."而非"一位创始人认为..."） |
| 4 | 视角基本准确，身份有体现 |
| 3 | 视角中性，未体现 Builder 身份 |
| 2 | 视角有偏差，可能误导读者对 Builder 立场的理解 |
| 1 | 张冠李戴，或与 Builder 身份明显矛盾 |

#### 维度 4：双语一致性（Bilingual Consistency）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 中英文信息完全一致，用词专业，英文不是中文的机器翻译 |
| 4 | 信息一致，表达有轻微差异 |
| 3 | 中英文侧重点略有不同，但不影响理解 |
| 2 | 中英文信息不对等，一方遗漏重要信息 |
| 1 | 中英文内容明显不同，或一方为空 |

#### 维度 5：可读性（Readability）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 语言简洁无歧义，中文符合母语表达，英文流畅自然，无"AI 味"翻译腔 |
| 4 | 可读性好，有个别不自然表达 |
| 3 | 基本可读，有少量翻译腔或冗余 |
| 2 | 阅读有障碍，翻译腔严重 |
| 1 | 语言混乱，无法正常阅读 |

---

### 3.2 综合评分等级

| 总分 | 等级 | 含义 |
| :--- | :--- | :--- |
| 23-25 | ⭐⭐⭐⭐⭐ 优秀 | 可直接用于展示，达到产品质量标准 |
| 18-22 | ⭐⭐⭐⭐ 良好 | 可用，有优化空间 |
| 13-17 | ⭐⭐⭐ 一般 | 信息可用但体验差，需改进 Prompt |
| 8-12 | ⭐⭐ 较差 | 需重写对应 Prompt 版本 |
| 1-7 | ⭐ 不可用 | 需排查 LLM 调用问题 |

---

### 3.3 评估方法

**方式一：抽样人工评估**
每次 Prompt 版本升级后，随机抽取 10 条摘要，按 5 个维度打分，计算平均分与上一版本对比。

**方式二：Bad Case 触发评估**
在 Feed 或 Archive 发现明显质量问题时，立即记录到 Bad Case 库，归因后对应升级 Prompt 版本。

**目标基准：**

| 指标 | 目标值 |
| :--- | :--- |
| 综合平均分 | ≥ 18 分（良好） |
| 维度 2 信息提炼度 | ≥ 4 分（核心指标） |
| 维度 1 分类准确率 | ≥ 4 分 |
| Bad Case 率 | < 10% |
