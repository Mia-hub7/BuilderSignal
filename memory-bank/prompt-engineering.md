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
| V1.1 | 拆分为独立调用；temperature=0.1 | 合并 prompt 导致调优变量耦合，无法独立优化摘要 | 分类单独一次调用（temperature=0.1，max_tokens=32）；`classify()` 函数独立 | 架构解耦，为 Round 2 摘要独立优化做准备 |
| V1.2 | 兜底规则改为返回 `off_topic` | 私人生活/情感内容被强制归类，污染 Feed | 排他规则末项从"选最接近类别"改为"完全无关内容返回 off_topic"；summarizer 检测到 skip 后不生成摘要、不展示 | 已验证：Garry Tan 私人帖、Nikunj 励志帖均正确识别为 off_topic |
| V1.3 | 类别边界重定义 + 两条新排他规则 | 全量回归扫描发现的 4 条 Bad Case（CLS-005~008）：产品动态与行业预判混淆、技术洞察与行业预判混淆 | ① 产品动态定义收窄为"明确宣布上线/交付"；② 行业预判扩展含"主观评论产品/公司运营"；③ 技术洞察加入"模型能力分析"；④ 新增两条排他规则 | 已废弃，被 V1.4 取代 |
| V1.4 | 分类体系重设计：4类→2类+off_topic | 4类边界天然模糊，Builder内容跨类是常态；bad case 根因是类别设计问题而非 prompt 问题 | 废弃技术洞察/产品动态/行业预判/工具推荐；改为「深度内容」（有具体可学/可用信息）vs「观点速览」（看法/预测/评论）；off_topic 保留；判断逻辑简化为一个核心问题 | 已废弃，被 V2.1 取代 |
| V2.1 | 去掉 off_topic，拿不准一律归"观点速览" | off_topic 过滤逻辑让模型多一个判断分支，短内容易被误判；实际上短内容/无关内容由 summarizer.py 的字符数检查兜底，分类层不再负责过滤 | 分类只保留两个选项（深度内容/观点速览）；off_topic 完全移除；拿不准时的 fallback 改为"选观点速览" | ✅ 生产运行中（2026-04-19），全库100条重跑验证通过 |

---

#### 1.A.2 历史版本完整内容

#### V1.1（当前生产，2026-04-16）

**System Prompt**
```
你是 BuilderSignal 的内容分类引擎。
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

**User Prompt Template**
```
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{"category": "技术洞察|产品动态|行业预判|工具推荐"}
```

**参数：** `temperature=0.1`，`max_tokens=32`

---

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

#### 1.A.4 历史版本归档（V1.4，2026-04-19，已废弃）

> 被 V2.1 取代。V1.4 保留 off_topic 选项，V2.1 移除。

#### System Prompt

```
你是 BuilderSignal 的内容分类引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

分类标准（只有三个选项，严格按照唯一判断规则执行）：

- 深度内容：内容包含具体的、可学习或可行动的信息
  包括：技术原理解释、工程实现方案、产品功能发布、工具推荐与使用方法、如何使用某模型/工具的具体技巧
  判断问题：读完这条内容，我能学到一个具体知识或找到一个可以用的东西吗？→ 能，则归此类

- 观点速览：内容是看法、预测、评论或感想，没有具体可学习的技术或产品信息
  包括：对 AI 趋势的判断、对竞争格局的评论、对某产品/公司的主观看法、行业观察、短句感慨
  判断问题：读完这条内容，我得到的是一个观点而非一个知识点吗？→ 是，则归此类

- off_topic：内容与 AI / 技术 / 产品完全无关（私人生活、情感、日常琐事、纯链接无内容）→ 返回 off_topic，不展示

排他规则：
- 既有具体信息又有观点 → 优先选"深度内容"
- 拿不准时问自己：这条能让我学到或用到什么具体东西吗？能 → 深度内容，否则 → 观点速览
```

#### User Prompt Template

```
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{"category": "深度内容|观点速览|off_topic"}
```

**参数：** `temperature=0.1`，`max_tokens=32`

---

#### 1.A.6 当前生产 Prompt（V2.1，2026-04-19）

> **变更说明：** 移除 off_topic 选项。短内容/无关内容的过滤职责下移至 `summarizer.py`（去除URL后字符数 < 30 → 直接翻译原文，不调 summarize）。分类层只负责二选一，拿不准时 fallback 为"观点速览"。

#### System Prompt

```
你是 BuilderSignal 的内容分类引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

分类标准（只有两个选项，严格按照唯一判断规则执行）：

- 深度内容：内容包含具体的、可学习或可行动的信息
  包括：技术原理解释、工程实现方案、产品功能发布、工具推荐与使用方法、如何使用某模型/工具的具体技巧
  判断问题：读完这条内容，我能学到一个具体知识或找到一个可以用的东西吗？→ 能，则归此类

- 观点速览：其他所有内容，包括看法、预测、评论、感想、私人动态、纯链接
  判断问题：不属于"深度内容"的 → 一律归此类

排他规则：
- 既有具体信息又有观点 → 优先选"深度内容"
- 拿不准时 → 选观点速览
```

#### User Prompt Template

```
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{"category": "深度内容|观点速览"}
```

**参数：** `temperature=0.1`，`max_tokens=32`

---

#### 1.A.5 历史版本归档（V1.3，已废弃）

#### System Prompt

```
你是 BuilderSignal 的内容分类引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

分类标准（严格按照定义执行，每条内容只能归属一个类别）：

- 技术洞察：涉及模型原理、工程架构、算法实现、技术路线判断，以及对特定模型技术能力的分析（某模型能做什么/做不到什么），即使带有评价或警示语气
  判断关键词：训练、推理、架构、参数、fine-tune、RAG、量化、benchmark、ability、capability
  示例：分析 Transformer vs RNN 的取舍、指出某模型在逆向工程上的能力边界

- 产品动态：明确宣布某产品/功能已上线或交付，包括"我们花了X时间终于做出了Y"这类交付声明
  判断关键词：launched、shipped、released、上线了、发布、新版本、v2.0、we built、we have、months of work
  示例：宣布新功能上线、分享历经数月打磨后的产品成果

- 行业预判：对 AI 未来趋势、竞争格局、产业变革的观点与预测，以及对产品/公司运营层面（故障、策略、市场动向）的主观评论
  判断关键词：未来、预测、我认为、趋势、会发生、机会在哪、I wonder、feels like、narrative
  示例：预测 Agent 的发展方向、评论某公司 AI 战略、观察某产品的稳定性问题

- 工具推荐：Builder 明确提及或推荐的具体工具、库、平台、服务
  判断关键词：推荐、在用、try this、check out、工具名称
  示例：推荐某个开源库、分享自己在用的开发工具

排他规则：
- 既有技术细节又有产品发布 → 优先选"产品动态"
- 既有工具又有技术解释 → 优先选"技术洞察"
- 分析某模型的技术能力（能/不能做什么）→ 技术洞察，即使语气带有警示或评价
- 对产品运营状况或公司策略的主观评论 → 行业预判，而非技术洞察
- 内容与 AI / 产品 / 行业 / 工具完全无关（如私人生活、情感内容、日常琐事）→ 返回 off_topic
```

#### User Prompt Template

```
Builder: {builder_name}（{builder_bio}）
平台: {source}
内容:
{raw_text}

只返回 JSON：{"category": "技术洞察|产品动态|行业预判|工具推荐|off_topic"}
```

**参数：** `temperature=0.1`，`max_tokens=32`

---

### 1.B 摘要 Prompt（Bilingual Summary）

> 目标：生成高质量中英双语摘要，2-4句，提炼核心观点，保留 Builder 第一人称视角。

#### 1.B.1 版本演进表

| 版本 | 核心指令 (Short Snippet) | 解决的问题 | 迭代策略 | 效果提升 |
| :--- | :--- | :--- | :--- | :--- |
| V0.2 | `"summary_zh": "中文摘要，2-4句"` | 基础摘要生成能力 | 仅给出字段说明，无视角要求，无格式约束 | 基线，能输出双语摘要 |
| V1.0 | （沿用 V0.2 摘要指令，无改动） | — | 本轮迭代专注分类标签，摘要部分未动 | 待 Round 2 展开 |
| V1.1 | 独立调用；Builder 视角要求；category 注入；temperature=0.4 | 合并调用无法独立调优摘要质量 | 摘要单独一次调用（temperature=0.4）；system prompt 明确视角/一致性/密度要求；user prompt 注入 category 实现类别感知摘要 | 架构解耦，temperature 提升流畅度，category 注入使摘要侧重与分类一致 |
| V2.0 | 【最重要】严禁第三人称；system prompt 加"禁止扩充"规则 | SUM-001：9/15条推文摘要被改成第三人称（"XX认为/指出"）；SUM-002：3/15条原文信息不足，摘要在编造/猜测内容 | ① system prompt 明确禁令：严禁"XX认为/指出/表示/该作者"，必须用"我/我们"；② 新增"禁止扩充"规则：原文有多少信息就写多少 | 已废弃，被 V2.1 取代 |
| V2.1 | 短内容改用 `translate()` 代替 skip；与分类 prompt 同步去掉 off_topic | V2.0 直接 skip 短内容导致这些条目无摘要无翻译，Feed 空白；off_topic 逻辑移出分类层后摘要层也需对应简化 | ① 去除 `is_processed=2` 的 skip 逻辑；② 短内容（去URL后 < 30字符）改为：直接存英文原文 + 调 `translate()` 生成中文；③ 新增独立 `TRANSLATE_SYSTEM`/`TRANSLATE_USER` prompt | ✅ 生产运行中（2026-04-19），全库100条重跑验证通过 |

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

##### V2.1（当前生产，2026-04-19）

**SUMMARIZE_SYSTEM**
```
你是 BuilderSignal 的摘要引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

摘要要求：
- 【最重要】必须用第一人称写作，严禁出现"XX认为"、"XX指出"、"XX表示"、"该作者"等第三人称表述。原文是"I think..."就用"我认为..."，原文是"We built..."就用"我们构建了..."
- 【禁止扩充】原文有多少信息就写多少，严禁推测、脑补或扩展原文未提及的内容
- 提炼核心观点，不复述原文，不堆砌套话
- 中英文信息完全一致，不能出现一方有另一方没有的内容
- 长度 2-4 句，宁短勿长，每句有实质内容
```

**SUMMARIZE_USER**
```
Builder: {builder_name}（{builder_bio}）
平台: {source}
分类: {category}
内容:
{raw_text}

只返回 JSON：
{
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
```

**参数：** `temperature=0.4`，`max_tokens=512`

**短内容专用 TRANSLATE_SYSTEM（新增）**
```
你是翻译引擎。将用户输入的英文内容翻译成中文。
规则：
- 只翻译，不解释，不扩展，不添加原文没有的信息
- 保留原文语气和标点
- 你必须只返回合法的 JSON，不含任何 Markdown 或额外说明
```

**TRANSLATE_USER**
```
内容：
{raw_text}

只返回 JSON：{"translation": "中文翻译"}
```

**参数：** `temperature=0.1`，`max_tokens=256`，仅用于去URL后 < 30 字符的短内容

---

##### V1.1（归档，2026-04-16）

**System Prompt**
```
你是 BuilderSignal 的摘要引擎。
你必须只返回合法的 JSON，不含任何 Markdown 或额外说明。

摘要要求：
- 保留 Builder 第一人称视角和语气，不要改写成第三人称描述
- 提炼核心观点，不复述原文，不堆砌套话
- 中英文信息完全一致，不能出现一方有另一方没有的内容
- 长度 2-4 句，宁短勿长，每句有实质内容
```

**User Prompt Template**
```
Builder: {builder_name}（{builder_bio}）
平台: {source}
分类: {category}
内容:
{raw_text}

只返回 JSON：
{
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
```

**参数：** `temperature=0.4`，`max_tokens=512`

---

##### V0.2（基线，2026-04-15）

> 摘要与分类合并在同一调用中，无独立 system prompt。

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

**参数：** `temperature=0.3`，`max_tokens=512`（与分类共用）

#### 1.B.3 技术攻坚复盘

**V1.1 → V2.0（Round 2，2026-04-19）**

**问题背景：**
从数据库随机抽取 15 条已有摘要（含 12 条 X 推文、3 条播客/博客），对照原文用简化三维度（①信息提炼度 ②Builder视角 ③双语一致性）评分，发现两个系统性问题。

**归因分析：**
- SUM-001 根因：V1.1 system prompt 对第一人称的要求措辞弱（"保留第一人称视角"），模型遇到 X 推文时默认用新闻报道语气改写，把"I think"改成"XX认为"。播客/博客内容反而保留了第一人称，因为原文本身是机构口吻的"我们"。
- SUM-002 根因：summarizer.py 没有内容充分性检查，把"banger + 链接"这类原文也送给 LLM，模型遇到信息不足时强行生成，产生猜测或无意义摘要。

**决策过程：**
- SUM-001：加强 prompt 禁令，列出具体禁止词（"XX认为/指出/表示/该作者"），比抽象要求更有执行力
- SUM-002：在代码层解决，不依赖 LLM 自我判断。去除 URL 后文本 < 30 字符直接跳过，与 off_topic 处理一致（is_processed=2）

**结果：** 待验证

---

## 二、Bad Case 归因库

### 2.1 分类标签 Bad Cases

> 表格说明：**AI 的判断** = 系统实际打出的标签；**正确答案** = 人工审核后应有的标签；**为什么出错** = 导致误判的根本原因；**状态** = 是否已通过版本迭代修复。

| 编号 | Builder 发布的内容 | AI 的判断 | 正确答案 | 为什么出错 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CLS-001 | Aditya Agarwal："The arc of a LLM skeptic: 1. just auto-correct 2. next-token predictors..." | 技术洞察 | 行业预判 | 内容里有"LLM"等技术词汇，AI 以为在讲技术原理，其实作者是在讲自己对 AI 认知的演变历程，属于观点与预测 | ✅ 已修复 |
| CLS-002 | Peter Steinberger："once again, I'm amazed by scammers. https://t.co/..." | （无标签，系统崩溃） | 行业预判 | 内容过短、只有一句话加一个链接，AI 无法做出判断，直接返回了空白，导致系统出错 | ✅ 已修复 |
| CLS-003 | Garry Tan："My grandma passed away today. She was 94 years old..." | 强行打上了行业标签 | 不展示（与 AI 无关） | 系统设计要求"看不懂就选个最近的类别"，导致奶奶去世这类私人内容被硬塞进行业分类，出现在用户的信息流里 | ✅ 已修复 |
| CLS-004 | Nikunj Kothari："Find someone who genuinely cares. A mentor. A founder. A VC..." | 技术洞察 | 不展示（与 AI 无关） | 励志/人生建议内容与 AI 完全无关，但同上，系统强行选了最接近的类别 | ✅ 已修复 |
| CLS-005 | Swyx："this is the year of subagents, but that is largely an optimization problem..." | 产品动态 | 行业预判 | 内容是对 AI Agent 趋势的观点评论，AI 看到"subagents"等词汇，误以为是某个产品的发布公告 | ✅ V1.3 修复（待回归验证） |
| CLS-006 | Swyx："in the grand narrative of Meta x AI, we saw the flop (Llama 4)..." | 产品动态 | 行业预判 | 内容是在分析 Meta 在 AI 赛道的战略格局，AI 看到产品名称，误以为是产品发布 | ✅ V1.3 修复（待回归验证） |
| CLS-007 | Nikunj Kothari："You can give system diagrams to Claude code and definitely one shot a lot of..." | 行业预判 | 技术洞察 | 内容是具体的 AI 工具使用技巧，AI 误把"如何使用 Claude"理解成了对行业趋势的判断 | ✅ V1.3 修复（待回归验证） |
| CLS-008 | Peter Yang："Feels like there's an outage for Claude every other day - I wonder if this is related to the pace of shipping..." | 技术洞察 | 行业预判 | 内容是作者对 Claude 频繁宕机的主观评论，AI 看到"outage（故障）"等词汇，误以为是技术原理的分析 | ✅ V1.3 修复（待回归验证） |

### 2.2 摘要 Bad Cases

> 表格说明：**AI生成的摘要** = 系统实际输出；**问题描述** = 哪里有问题；**为什么出错** = 根本原因；**状态** = 是否修复。

| 编号 | Builder 发布的内容 | AI 生成的摘要 | 问题描述 | 为什么出错 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SUM-001 | Thariq："The 1M context window is a double-edged sword..."（以及其他9条X推文） | "Thariq指出Claude的100万上下文窗口是双刃剑……" | 15条样本中9条摘要把第一人称改成了第三人称（"XX认为/指出/表示"），原文"I think..."变成"XX认为..." | V1.1 system prompt 只写了"保留第一人称"，约束力不足，模型将X推文当作新闻事件用报道语气改写 | ✅ V2.0 修复：加强禁令，明确列出禁止词 |
| SUM-002 | Dan Shipper："banger https://t.co/..."；Swyx："grateful to @steipete... https://..."；Amjad Masad："I've been really enjoying this feature..." | "推测可能是与AI相关的优质工具或资源推荐"（编造）；直接复述原文（无实质信息） | 3条原文信息极少（去除链接后仅剩几个词），摘要要么在猜测编造内容，要么直接复述毫无价值 | 之前没有内容充分性检查，summarizer直接把所有内容送给LLM，LLM遇到信息不足时强行生成 | ✅ V2.0 修复：summarizer.py 调LLM前先检查：去除URL后文本<30字符→跳过，不生成摘要 |
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
