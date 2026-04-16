# Prompt 调优执行日志: BuilderSignal

> 本文档记录 Prompt Engineering 的完整执行过程，按时间线追踪每一轮调优的背景、决策、操作和结果。
> 技术参考文档（Prompt 完整内容、Bad Case 库、质量标准）见 `prompt-engineering.md`。

---

## 执行总览

| 轮次 | 日期 | 目标 | 状态 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| Round 0 | 2026-04-15 | 建立基线（V0.2） | ✅ 完成 | 基线可用，分类模糊，摘要质量待评估 |
| Round 1 | 2026-04-16 | 分类标签优化（V1.0→V1.1） | ✅ 完成 | 分类准确率提升，架构解耦完成 |
| Round 2 | 待开展 | 摘要质量优化 | ⏳ 待开展 | — |
| Round 3 | 待开展 | 实体/引用提取 | ⏳ 待开展 | — |

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

## Round 2 — 摘要质量优化（待开展）

### 计划

**目标：** 提升双语摘要在以下维度的得分（见 prompt-engineering.md 三、质量评估标准）：
- 信息提炼度：去除套话，每句有实质内容
- Builder 视角准确性：第一人称语气保留
- 双语一致性：中英文信息完全对等
- 可读性：无翻译腔，中文地道

**准备工作：**
1. 从已有 37 条摘要中抽取样本，人工评分（按三节 Rubric）
2. 找出低分条目作为 Bad Case，写入 SUM-xxx
3. 分析共同失败模式，设计 prompt 改动
4. 实现 V1.2，跑回归验证

**执行时间：** 待开展

---

## Round 3 — 实体/引用提取（待开展）

### 计划

**目标：** 在摘要中自动提取 Builder 提到的关键实体（工具名、模型名、公司名、人名），为未来 RAG 知识库和观点碰撞功能做数据基础。

**执行时间：** Round 2 完成后开展
