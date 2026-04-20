# Prompt 调优执行日志: BuilderSignal

> 本文档记录 Prompt Engineering 的完整执行过程，按时间线追踪每一轮调优的背景、决策、操作和结果。
> 技术参考文档（Prompt 完整内容、Bad Case 库、质量标准）见 `prompt-engineering.md`。

---

## 执行总览

| 轮次 | 日期 | 目标 | 状态 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| Round 0 | 2026-04-15 | 建立基线（V0.2） | ✅ 完成 | 基线可用，分类模糊，摘要质量待评估 |
| Round 1 | 2026-04-16 | 分类标签优化（V1.0→V1.4） | ✅ 完成 | 架构解耦，分类体系重设计：4类→2类（深度内容/观点速览），去掉 off_topic |
| Round 2 | 2026-04-19 | 摘要质量优化（V2.0→V2.1） | ✅ 完成 | V2.0：第一人称禁令（禁止"XX认为/指出"）、禁止扩充；V2.1：去掉 off_topic，短内容改用 translate() 代替 skip，全库100条重新生成 |
| Round 3 | 暂缓 | 实体/引用提取 | 🔵 暂缓 | 功能本身可行，但对日常使用无直接价值，待 Phase 3 RAG 知识库启动时再做 |

---

## Round 0 — 建立基线（2026-04-15）

### 背景

项目 MVP 上线，需要最快速度跑通 LLM 处理链路。分类与摘要合并为一次调用，用最简单的 Prompt 验证可行性。

### 操作

- 实现 `processor/claude_client.py`，单次调用同时完成分类 + 双语摘要
- Prompt 设计极简：system prompt 说明角色，user prompt 列出 4 个类别选项 + 摘要格式要求
- 温度统一设为 `0.3`，max_tokens=512

### 基线 Prompt 核心设计

```
system: 你是一个专业的 AI 行业内容分析师...
user:   请对内容进行分类，返回 {"category": "技术洞察|产品动态|行业预判|工具推荐", "summary_zh": ..., "summary_en": ...}
```

### 结果

- ✅ 链路跑通，37 条内容全部正常入库
- ✅ 双语摘要可以生成
- ⚠️ 未做质量评估，分类准确率未知
- ⚠️ 偶发空值 bug（Peter Steinberger 短推文返回空 category）

### 遗留问题

1. 分类类别无定义，模型依赖猜测，边界类内容（如"技术洞察"vs"行业预判"）准确率低
2. 无 builder 身份信息注入，模型无角色上下文
3. 分类与摘要耦合，无法独立调优

---

## Round 1 — 分类标签优化（2026-04-16）

### 阶段一：问题发现

**触发：** 手动审查 10 条样本，发现 Aditya Agarwal 的"The arc of a LLM skeptic"被分类为"技术洞察"，但内容是对 AI 认知演变的观点预测，应为"行业预判"。

**分析过程：**
- V0.2 system prompt 无任何类别定义，4 个类别对模型而言只是标签名称
- "LLM"这个词触发模型联想到技术内容，导致误分类
- 同时发现 Peter Steinberger 的短链接推文返回空字符串（格式 bug）

**记录：** → Bad Case CLS-001、CLS-002（见 prompt-engineering.md 2.1）

---

### 阶段二：方案设计

**核心决策：**
1. 为每个类别写明确定义 + 判断关键词 + 示例内容
2. 增加排他优先级规则，解决多类别交叉问题
3. 注入 `builder_bio`（如"前 OpenAI / Tesla AI"），给模型角色上下文
4. 增加兜底规则：任何内容必须归入最接近的一类，禁止返回空值

**设计原则：** 每次只改一个变量，这次只改分类 prompt，不动摘要部分。

---

### 阶段三：实现 V1.0

**改动文件：** `processor/claude_client.py`

- SYSTEM_PROMPT：加入四类定义、关键词、示例、排他规则、兜底规则
- USER_PROMPT_TEMPLATE：`{builder_name}` + `{builder_bio}` 注入
- `summarizer.py`：查询 `builder.bio` 传入 `call_llm()`

**commit：** `b70c8bb` — feat: upgrade classification prompt to V1.0

---

### 阶段四：验证测试

**工具：** `processor/prompt_test.py`（对比 V0.2 vs V1.0 在同一批数据上的输出）

**测试集：** 10 条最新 Supabase 数据

**结果：**

| ID | Builder | 内容摘要 | V0.2 | V1.0 | 判断 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 37 | AI & I by Every | The AI Model Built for What LLMs Can't Do | 技术洞察 | 技术洞察 | ✅ 一致 |
| 36 | Aditya Agarwal | The arc of a LLM skeptic... | 技术洞察 | 行业预判 | ✅ V1.0 更准 |
| 35 | Dan Shipper | Spotify/YouTube 链接 | 工具推荐 | 工具推荐 | ✅ 一致 |
| 34 | Dan Shipper | everything is coding agent... | 行业预判 | 行业预判 | ✅ 一致 |
| 33 | Dan Shipper | banger + 链接 | 工具推荐 | 产品动态 | ⚠️ 内容截断无法判断 |
| 32 | Peter Steinberger | once again, I'm amazed by scammers... | (空值) | 行业预判 | ✅ V1.0 修复 bug |
| 31 | Peter Steinberger | GPT 5.4-Cyber reverse engineering... | 技术洞察 | 技术洞察 | ✅ 一致 |
| 30 | Peter Steinberger | 4 months and thousands of work hours... | 产品动态 | 产品动态 | ✅ 一致 |
| 29 | Nikunj Kothari | You can give system diagrams to Claude... | 技术洞察 | 技术洞察 | ✅ 一致 |
| 28 | Nikunj Kothari | Find someone who genuinely cares... | 行业预判 | 行业预判 | ✅ 一致 |

**汇总：** 10条，7条一致，3条变化，2条确认 V1.0 更优，1条截断无法判断

**结论：** V1.0 分类准确率提升，部署生产。

---

### 阶段五：架构解耦（V1.1）

**触发：** Round 2 摘要优化计划启动前，发现分类与摘要耦合存在以下问题：
- 改分类规则会连带影响摘要输出，反之亦然
- 合并调用只能用一个 temperature（0.3），是妥协值：分类需要确定性（低温），摘要需要流畅度（中温）
- 回归测试时分类 PASS/FAIL 会受摘要质量波动影响

**决策：** 在 Round 2 开始前完成拆分，保证摘要调优从第一天起就在干净的变量下进行。

**改动内容（`processor/claude_client.py`）：**

```
新增 classify()   → temperature=0.1, max_tokens=32
                    只负责返回 category 字符串
新增 summarize()  → temperature=0.4, max_tokens=512
                    接收 category 参数，生成 category-aware 摘要
保留 call_llm()   → 串行调用 classify() + summarize()
                    summarizer.py 接口不变
```

**关键改进：**
- 摘要 system prompt 首次明确 Builder 视角要求、双语一致性要求
- user prompt 注入 `{category}`，摘要根据分类类型调整侧重（技术洞察偏原理，行业预判偏观点）
- temperature 分别优化：分类 0.1（确定性），摘要 0.4（流畅度）

**本地验证：**
```
classify("Anthropic", "x", "We just shipped a new Claude...") → 产品动态 ✅
summarize(..., category="产品动态") → 保留第一人称"我们刚发布" ✅
call_llm("Andrej Karpathy", "x", "Fine-tuning is overrated. RAG solves 80%...")
  → category: 技术洞察, summary_zh: "我认为微调被高估了。RAG能以低成本解决80%的使用场景。" ✅
```

**commit：** `f7859f6` — refactor: split LLM into separate classify + summarize calls

---

### Round 1 总结

| 指标 | 基线 V0.2 | V1.1（当前） |
| :--- | :--- | :--- |
| 空值 bug | 偶发 | 已修复 |
| 分类 temperature | 0.3（合并） | 0.1（独立） |
| 摘要 temperature | 0.3（合并） | 0.4（独立） |
| Builder 身份注入 | 无 | ✅ bio 注入 |
| Category-aware 摘要 | 无 | ✅ category 注入 |
| 调优变量隔离 | 无 | ✅ 完全解耦 |
| 10条测试准确率 | 未测 | 9/10（1条截断无法判断） |

**待进入 Round 2：** 摘要质量专项优化

---

---

### 阶段六：off_topic 过滤（V1.2，2026-04-16）

**触发：** 线上 Feed 发现两条明显错误分类：
- Garry Tan 奶奶去世帖被强制归类展示
- Nikunj Kothari 励志/职场建议帖被归为"技术洞察"

**根因：** V1.1 兜底规则"无法归入四类 → 选最接近的一类"对完全无关内容不适用，导致私人和励志内容污染 Feed。

**决策：** 不新增"其他"可见分类（避免垃圾桶效应），而是加 `off_topic` 内部标记：
- 内容仍入库（保持 Track the Builders 原则）
- `is_processed=2`，不生成摘要，不出现在 Feed/Archive

**改动：**
- `CLASSIFY_SYSTEM`：兜底规则改为"完全无关内容 → 返回 off_topic"
- `CLASSIFY_USER`：category 选项加入 `off_topic`
- `call_llm()`：检测到 off_topic 直接返回 `{"skip": True}`
- `summarizer.py`：检测到 skip 跳过摘要生成，设 `is_processed=2`

**验证：**
```
classify("Garry Tan", "x", "My grandma passed away today...") → off_topic ✅
classify("Nikunj Kothari", "x", "Find someone who genuinely cares...") → off_topic ✅
```

**Bad Cases 记录：** → CLS-003、CLS-004（见 prompt-engineering.md 2.1）

---

### Round 1 总结（更新）

| 指标 | 基线 V0.2 | V1.3（当前） |
| :--- | :--- | :--- |
| 空值 bug | 偶发 | 已修复 |
| 无关内容展示 | 强制归类展示 | off_topic 过滤不展示 |
| 产品名/趋势词触发产品动态误判 | 存在 | V1.3 收窄定义修复 |
| 模型能力分析 vs 行业预判混淆 | 存在 | V1.3 新排他规则修复 |
| 分类 temperature | 0.3（合并） | 0.1（独立） |
| 摘要 temperature | 0.3（合并） | 0.4（独立） |
| Builder 身份注入 | 无 | ✅ bio 注入 |
| Category-aware 摘要 | 无 | ✅ category 注入 |
| 调优变量隔离 | 无 | ✅ 完全解耦 |

---

### 阶段七：类别边界重定义（V1.3，2026-04-17）

**触发：** 全量回归扫描（`regression_test.py --scan`）发现 4 条新 Bad Case（CLS-005~008），根因均为类别定义不够精确导致边界混淆。

**失败模式分析：**
- **产品名 / 技术词 → 误判产品动态**（CLS-005、CLS-006）：V1.2 产品动态定义宽泛，含有产品名称/技术词汇的观点帖被误归入
- **工具使用技巧 → 误判行业预判**（CLS-007）：如何使用 Claude 的具体技巧，AI 误认为是趋势评论
- **服务故障评论 → 误判技术洞察**（CLS-008）：含 "outage" 词汇被联想到技术原理

**改动内容（`processor/claude_client.py`）：**

```
产品动态定义：收窄为"明确宣布某产品/功能已上线或交付"，加入 we built、months of work 等交付信号词
行业预判定义：扩展含"对产品/公司运营层面的主观评论"，加入 I wonder、feels like、narrative 等关键词
技术洞察定义：加入"对特定模型技术能力的分析（能/不能做什么）"，加入 ability、capability
排他规则新增两条：
  - 分析某模型的技术能力 → 技术洞察（即使语气带有评价）
  - 对产品运营状况或公司策略的主观评论 → 行业预判（而非技术洞察）
```

**状态：** 已更新代码，待运行回归测试确认

**下一步：**
1. 把 CLS-005~008 的数据库 ID 填入 `golden_set.json`（运行 `python processor/regression_test.py --scan` 获取）
2. 运行回归：`python processor/regression_test.py`，确认全部 PASS
3. 提交 V1.3 commit，然后开始 Round 2

---

## Round 2 — 摘要质量优化（待开展）

### 计划

**前置条件：** V1.3 回归测试通过，commit 完成。

**目标：** 提升双语摘要在以下维度的得分（见 prompt-engineering.md 三、质量评估标准）：
- 信息提炼度：去除套话，每句有实质内容
- Builder 视角准确性：第一人称语气保留
- 双语一致性：中英文信息完全对等
- 可读性：无翻译腔，中文地道

**执行步骤（有序）：**

**Step 1 — 采样与评分**
- 从数据库随机抽取 15 条已有摘要（覆盖 4 个分类，含 X 和 RSS 来源）
- 按 prompt-engineering.md 三节 Rubric 人工逐条评分（5个维度，满分 25 分）
- 目标：找出评分 ≤ 17 分（"一般"及以下）的条目作为 Bad Case

**Step 2 — Bad Case 分析**
- 将低分条目写入 prompt-engineering.md 2.2 摘要 Bad Cases（SUM-001, SUM-002...）
- 每条记录：原始内容、AI 摘要、问题描述、失败根因
- 归纳共同失败模式（如：翻译腔、套话、中英信息不对等等）

**Step 3 — Prompt 迭代**
- 针对最高频失败模式修改 `SUMMARIZE_SYSTEM` 和/或 `SUMMARIZE_USER`
- 版本命名：V2.0（摘要 prompt 首次独立大改）
- 每次只改一处变量

**Step 4 — 验证**
- 对比 V1.3 vs V2.0 在同一批样本上的摘要输出，重新评分
- 目标：综合平均分 ≥ 20/25，维度2信息提炼度 ≥ 4/5

**执行时间：** 2026-04-17 起

---

## Round 3 — 实体/引用提取（待开展）

### 计划

**目标：** 在摘要中自动提取 Builder 提到的关键实体（工具名、模型名、公司名、人名），为未来 RAG 知识库和观点碰撞功能做数据基础。

**执行时间：** Round 2 完成后开展
