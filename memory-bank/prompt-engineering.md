# Prompt Engineering 调优文档: BuilderSignal

| 版本 | 日期 | 作者 |
| :--- | :--- | :--- |
| v1.0 | 2026-04-16 | Mia |

---

## 零、工程化调优工作流

### 0.1 工作流定义

```
发现 Bad Case
    ↓
  [工具] regression_test.py 全量扫描
  [输出] 每条内容的 predicted 分类
  [操作] 人工审阅，标注 expected，写入 golden_set.json

分析原因（Root Cause）
    ↓
  [操作] 逐条分析 predicted ≠ expected 的原因
  [分类] 类别定义模糊 / 缺乏排他规则 / 截断信息不足 / 模型幻觉
  [记录] 写入 Bad Case 归因库（第二节）

迭代 Prompt
    ↓
  [操作] 针对 Root Cause 修改 claude_client.py 中的 SYSTEM_PROMPT 或 USER_PROMPT_TEMPLATE
  [原则] 每次只改一处，保持变量隔离，便于归因
  [记录] 写入版本演进表（1.1），归档完整 Prompt（1.2）

验证回归（Regression）
    ↓
  [工具] regression_test.py 对比 golden_set.json
  [指标] 准确率 ≥ 目标值（3.3 节），且无新增 FAIL
  [条件] 所有旧 PASS 保持通过 + 新 Bad Case 修复 → 才可部署
  [记录] 将回归结果写入对应版本的「结果」字段
```

### 0.2 工具清单

| 文件 | 用途 |
| :--- | :--- |
| `processor/regression_test.py` | 主测试工具：全量扫描 + Golden Set 对比 + PASS/FAIL 统计 |
| `processor/golden_set.json` | 人工打标的标准答案集，每条含 `id / expected / note` |
| `processor/prompt_test.py` | 快速对比两个 Prompt 版本（用于探索阶段，非回归） |
| `memory-bank/prompt-engineering.md` | 本文档：迭代记录 + Bad Case 库 + 质量标准 |

### 0.3 Golden Set 维护原则

- 每次发现新 Bad Case，**先修复 golden_set.json 再修改 Prompt**，避免覆盖问题
- `note` 字段必须填写，说明为什么这条的正确分类是 expected（是后续 Root Cause 分析的依据）
- 每轮迭代后保留所有历史条目，不删除已 PASS 的条目（防止回归）
- 目标：Golden Set 达到 30 条以上才能代表真实分布

---

## 一、Prompt 迭代记录

---

### 1.A 分类标签 Prompt（Category Tagging）

#### 1.A.1 版本演进表

| 版本 | 核心指令 (Short Snippet) | 解决的问题 | 迭代策略 | 效果提升 |
| :--- | :--- | :--- | :--- | :--- |
| V0.1 | — | — | — | 基线版本 |
| V0.2 | `"category": "技术洞察\|产品动态\|行业预判\|工具推荐"` | 基础分类能力 | 仅列出四个类别选项，无定义，无示例 | 基线，能输出合法 JSON |
| V1.0 | 分类标准 + 关键词 + 排他规则 + builder_bio 注入 | V0.2 分类模糊，行业预判 vs 技术洞察混淆；偶发空值 bug | 为每个类别添加定义、判断关键词、示例；增加排他优先级规则；将 builder_bio 注入 user prompt | 10条样本测试：3条变化，2条 V1.0 明确更准（行业预判识别、空值修复），1条截断内容无法判断 |

---

#### 1.A.2 历史版本完整内容

#### V0.2（基线，2026-04-15）

**System Prompt**
```
你是一个专业的 AI 行业内容分析师。
你的任务是对 AI Builder 发布的内容进行分类。
你必须只返回合法的 JSON，不要包含任何 Markdown 代码块或额外说明。
```

**User Prompt Template**
```
以下是 {builder_name} 在 {source} 上发布的内容：

{raw_text}

请对内容进行分类，返回以下 JSON：
{"category": "技术洞察|产品动态|行业预判|工具推荐"}

只返回 JSON。
```

> 注：V0.2 分类 prompt 与摘要 prompt 是合并在一个 `claude_client.py` 调用里的，完整 user prompt 还包含 summary_zh 和 summary_en 字段的输出要求（见 `processor/prompt_test.py` classify_v02 函数）。

---

#### 1.A.3 技术攻坚复盘

**问题背景：**
V0.2 Prompt 仅列出 4 个类别标签，无定义、无示例、无消歧规则。测试发现对"观点预测类"内容（如 LLM 认知演变的讨论）误分类为"技术洞察"；对极短/截断内容偶发返回空字符串（非合法 JSON key value）。

**归因分析：**
- 类别边界模糊："技术洞察"与"行业预判"在无定义情况下高度重叠，模型依赖上下文猜测
- 无 builder 身份信息：缺乏 bio 导致模型无法利用 builder 角色信息做更准确的分类
- 无排他规则：多类别交叉内容时模型无法决策

**决策过程：**
1. 为每个类别编写明确定义 + 判断关键词列表 + 示例内容
2. 增加排他优先级规则（产品动态 > 技术细节；技术洞察 > 工具说明）
3. 在 user prompt 中注入 `builder_bio`（如"前 OpenAI / Tesla AI"）以提供角色上下文
4. 兜底规则：无法归类内容仍选最接近类别，避免空值

**结果：**
- 测试集 10 条，V1.0 vs V0.2 有 3 条分类变化
- [36] Aditya Agarwal "The arc of a LLM skeptic"：V0.2=技术洞察 → V1.0=行业预判 ✅ 更准
- [32] Peter Steinberger（链接内容）：V0.2=空值 → V1.0=行业预判 ✅ 修复 bug
- [33] Dan Shipper "banger + 链接"：V0.2=工具推荐 → V1.0=产品动态（内容截断无法判断优劣）
- V1.0 已部署至生产 `processor/claude_client.py`

---

#### 1.A.4 当前生产 Prompt

#### System Prompt

```
你是 BuilderSignal 的内容分类与摘要引擎。
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
- 无法归入以上四类（如日常生活、无实质内容）→ 仍选最接近的一类
```

#### User Prompt Template

```
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

请对内容进行分类并生成双语摘要，只返回 JSON：
{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
```

---

### 1.B 摘要 Prompt（Bilingual Summary）

> 目标：生成高质量中英双语摘要，2-4句，提炼核心观点，保留 Builder 第一人称视角。

#### 1.B.1 版本演进表

| 版本 | 核心指令 (Short Snippet) | 解决的问题 | 迭代策略 | 效果提升 |
| :--- | :--- | :--- | :--- | :--- |
| V0.2 | `"summary_zh": "中文摘要，2-4句"` | 基础摘要生成能力 | 仅给出字段说明，无视角要求，无格式约束 | 基线，能输出双语摘要 |
| V1.0 | （沿用 V0.2 摘要指令，无改动） | — | 本轮迭代专注分类标签，摘要部分未动 | 待 Round 2 展开 |

#### 1.B.2 历史版本完整内容

##### V0.2（基线，2026-04-15）

**User Prompt Template（摘要部分）**
```
请完成以下任务：
对内容进行分类，并生成双语摘要，返回以下 JSON：
{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
只返回 JSON，不要包含任何其他内容。
```

##### V1.0（当前生产，2026-04-16）

> 摘要指令沿用 V0.2，尚未专项优化，Round 2 将针对摘要质量展开迭代。

**User Prompt Template（摘要部分）**
```
请对内容进行分类并生成双语摘要，只返回 JSON：
{
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
```

#### 1.B.3 技术攻坚复盘

**V1.0 → V1.1（待开展，Round 2）**

**问题背景：** （待 Round 2 跑完后填写）

**归因分析：** （待填写）

**决策过程：** （待填写）

**结果：** （待填写）

---

## 二、Bad Case 归因库

### 2.1 分类标签 Bad Cases

| 案例 ID | 原始输入 (Context) | 模型错误输出 (Bad Output) | 错误类型 | 归因分析 (Root Cause) | 解决方案 (Fix) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CLS-001 | [36] Aditya Agarwal, x: "The arc of a LLM skeptic: 1. just auto-correct 2. next-token predictors 3. ..." | category: "技术洞察" | 分类错误 | V0.2 无类别定义，"LLM" 触发技术洞察，但内容是对 AI 认知演变的观点预测，属行业预判 | V1.0 增加行业预判定义和排他规则，修复 |
| CLS-002 | [32] Peter Steinberger, x: "once again, I'm amazed by scammers. https://t.co/..." | category: "" (空值) | 输出格式错误 | V0.2 对内容太短/仅含链接的推文无法决策，返回空字符串 | V1.0 增加兜底规则"仍选最接近的一类"，修复 |

### 2.2 摘要 Bad Cases

| 案例 ID | 原始输入 (Context) | 模型错误输出 (Bad Output) | 错误类型 | 归因分析 (Root Cause) | 解决方案 (Fix) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SUM-001 | — | — | — | — | — |

---

## 三、质量评估标准（The Rubric）

### 3.1 评分维度（5项，每项1-5分，满分25分）

#### 维度 1：分类准确性（Category Accuracy）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 分类与内容语义完全一致，无歧义 |
| 4 | 分类合理，存在一定边界模糊但可接受 |
| 3 | 分类有争议，另一类别同样合理 |
| 2 | 分类明显偏差，与内容主旨不符 |
| 1 | 分类完全错误，或返回空值 |

#### 维度 2：信息提炼度（Insight Density）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 摘要精准捕捉核心观点，无冗余，有实质性洞察 |
| 4 | 摘要覆盖主要观点，偶有泛化表述 |
| 3 | 摘要大体准确但信息密度不足，存在套话 |
| 2 | 摘要过于宽泛，未提取实质内容 |
| 1 | 摘要与原文无关，或仅复述原文 |

#### 维度 3：Builder 视角准确性（Author Perspective）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 清晰保留 Builder 第一人称观点，语气与原文一致 |
| 4 | 基本保留观点，轻微平滑处理 |
| 3 | 观点有所保留但角度偏移 |
| 2 | 变成第三方描述，丢失 Builder 主体性 |
| 1 | 完全中性化，看不出是 Builder 的观点 |

#### 维度 4：双语一致性（Bilingual Consistency）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 中英文摘要信息完全一致，措辞精准对应 |
| 4 | 中英文主要信息一致，细节略有差异 |
| 3 | 中英文有明显内容差异（一方有另一方没有） |
| 2 | 中英文差异较大，需分别阅读 |
| 1 | 中英文互相矛盾，或其中一方为空/无意义 |

#### 维度 5：可读性（Readability）

| 分值 | 标准 |
| :--- | :--- |
| 5 | 表达流畅，无机器翻译感，中文地道，英文自然 |
| 4 | 基本流畅，偶有生硬表达 |
| 3 | 可读但有明显翻译腔或结构生硬 |
| 2 | 阅读障碍较多，需多次阅读才能理解 |
| 1 | 不可读，语句不通顺 |

---

### 3.2 综合评分等级

| 总分 | 等级 | 含义 |
| :--- | :--- | :--- |
| 23-25 | ⭐⭐⭐⭐⭐ 优秀 | 可直接使用，无需修改 |
| 18-22 | ⭐⭐⭐⭐ 良好 | 基本可用，偶尔需要微调 |
| 13-17 | ⭐⭐⭐ 一般 | 需要人工审核后使用 |
| 8-12 | ⭐⭐ 较差 | 需要大量修改，考虑重新生成 |
| 1-7 | ⭐ 不可用 | 质量不达标，直接丢弃 |

---

### 3.3 目标基准

| 指标 | 目标值 |
| :--- | :--- |
| 综合平均分 | ≥ 20 / 25 |
| 维度 2 信息提炼度 | ≥ 4 / 5 |
| 维度 1 分类准确率 | ≥ 90%（10条中 ≥ 9条正确） |
| Bad Case 率 | ≤ 10% |
