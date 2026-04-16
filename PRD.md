# 产品需求文档 (PRD): BuilderSignal (匠心信标)

| 版本 | 状态 | 修订日期 | 负责人 |
| :--- | :--- | :--- | :--- |
| v1.1 | 草案 | 2026-04-15 | AI PM |
| v1.2 | 已更新 | 2026-04-16 | AI PM |

---

## 1. 产品概览 (Product Overview)

* **一句话定义**：一个专注 AI 领域"建设者"（Builders）一手深度内容的自动化追踪与摘要系统。
* **核心价值**：过滤营销噪音，打破信息茧房，让用户通过最少的时间成本，直接获取全球顶尖 AI 大脑的原始认知与决策逻辑。
* **产品理念**：**Track the Builders, Skip the Influencers.**
* **使用场景**：个人使用，单用户，非商业产品。

---

## 2. 目标用户 (Target Audience)

本产品为**个人自用工具**，目标用户即开发者本人，具备以下特征：

* AI 从业者，需要紧跟技术演进（如 RAG, Agentic Workflow）的产品/工程视角
* 关注头部实验室核心人员（OpenAI, Anthropic 等）的一手思考
* 希望建立底层技术直觉，避开二手营销信息

---

## 3. 用户痛点 (User Problems)

1. **低信噪比**：社交平台充满大量为流量搬运的"二手网红"，原创硬核观点被掩埋。
2. **跨平台采集难**：Builders 的观点散落在 X (Twitter)、YouTube 播客、Substack 及公司技术博客，手动追踪成本极高。
3. **长内容消化难**：顶尖 Builder 的思考往往隐藏在 2 小时访谈或大量推文中，缺乏结构化提炼。

---

## 4. 核心功能模块 (Core Features)

### 4.1 动态白名单系统 (Smart Whitelist)

* **内置白名单**：系统预置 33 位核心 AI Builder（25个X账号 + 6个播客 + 2个博客）。
* **用户自定义扩展**：用户可在 Settings 页面添加/禁用/删除 Builder。
* **准入标准参考**：顶级 AI 公司创始人、核心工程师、研究员，或具有公认原创能力的 Builder。
* **验收标准**：✅ 用户可在 Dashboard 增删账号，变更实时生效，下次抓取周期自动纳入。

### 4.2 全渠道内容抓取 (Multi-source Ingestion)

| 渠道 | 方案 | 状态 |
| :--- | :--- | :--- |
| X (Twitter) | follow-builders 公开 GitHub Feed（无需 X API Key） | ✅ |
| 企业/个人博客 | follow-builders 公开 GitHub Feed（blog JSON） | ✅ |
| YouTube / Podcast | follow-builders Feed + Supadata API 转录（transcript 为空时补充） | ✅ |

* **数据来源**：消费 [follow-builders](https://github.com/zarazhangrui/follow-builders) 公开 JSON Feed，每日 UTC 06:00 更新。
* **抓取频率**：每天一次（Render Cron Job，UTC 22:00 / 北京时间 06:00）。
* **去重逻辑**：基于 content_id（SHA-256 hash），避免重复入库。

### 4.3 AI 驱动内容处理 (AI Processing)

* **LLM**：豆包 API（火山引擎 ARK，deepseek-chat 模型，OpenAI 兼容协议）
* **内容策略**：白名单内所有内容直接入库，不做 LLM 过滤（Track the Builders 原则）
* **分类标签**：每条内容自动打标，支持以下类别过滤：
  * `技术洞察` — 算法、架构、工程实现
  * `产品动态` — 新功能、产品发布、路线图
  * `行业预判` — 对未来趋势的观点与预测
  * `工具推荐` — Builder 提到的工具、库、服务
* **结构化摘要（双语）**：
  * **中文摘要**：2-4句，提炼核心观点
  * **英文摘要**：2-4 sentences, extracting key insights
  * **原文链接**：每条摘要附带原文跳转链接
* **验收标准**：✅ 摘要输出为中英双语，含分类标签和原文链接

### 4.4 Web Dashboard

* **技术栈**：FastAPI + Jinja2 + TailwindCSS CDN + HTMX
* **核心页面**：
  * **Feed 首页** ✅：展示最新摘要卡片，支持分类筛选，无数据时自动回退到最近一次内容
  * **Archive 归档页** ✅：按日期浏览历史摘要，支持关键词搜索（摘要内容 + Builder 名字）
  * **Settings 页** ✅：Builder 白名单管理（增删启禁），操作成功/失败 toast 提示
* **验收标准**：✅ 可在浏览器访问，响应时间 < 3s，移动端可阅读

### 4.5 自动化定时任务 (Scheduled Jobs)

* **抓取任务**：每天 UTC 22:00（北京 06:00）自动触发，确保早上 09:00 有当日内容
* **清理任务**：每天 UTC 18:00（北京 02:00）清理 30 天前的历史数据
* **手动触发**：`POST /api/trigger-fetch` 支持手动触发完整抓取流程
* **注**：Daily Digest 置顶推送功能尚未实现，列入 Phase 3

---

## 5. 核心资产：Builder 白名单 (Default Whitelist)

| 类别 | 姓名 | 所属公司 / 身份 |
| :--- | :--- | :--- |
| **实验室/大厂核心** | Sam Altman | OpenAI CEO |
| | Kevin Weil | OpenAI CPO |
| | Andrej Karpathy | 前 OpenAI / Tesla AI |
| | Amanda Askell | Anthropic 研究员 (Alignment) |
| | Alex Albert | Anthropic (Claude Relations) |
| | Josh Woodward | Google Labs VP |
| | Claude (Official) | Anthropic 官方账号 |
| **独角兽/平台创始人** | Amjad Masad | Replit CEO |
| | Guillermo Rauch | Vercel CEO |
| | Aaron Levie | Box CEO |
| | Garry Tan | YC CEO |
| **硬核 Builder / 极客** | Ryo Lu | Cursor 设计负责人 |
| | Peter Steinberger | PSPDFKit 创始人 |
| | Nan Yu / Madhu Guru | AI Builders |
| | Cat Wu / Thariq | AI Builders |
| | Nikunj Kothari | AI Builder |
| **行业布道与观察** | Swyx (Shawn Wang) | Latent Space 联创 |
| | Dan Shipper | Every.to CEO |
| | Peter Yang | AI 产品 Creator |
| | Matt Turck | FirstMark Capital 合伙人 |
| | Aditya Agarwal | 前 Dropbox CTO |
| | Zara Zhang | GGV Capital 投资人 |
| **播客** | Latent Space | AI 播客 |
| | Training Data | AI 播客 |
| | No Priors | AI 播客 |
| | Unsupervised Learning | AI 播客 |
| | The MAD Podcast | Matt Turck 主持 |
| | AI & I by Every | Dan Shipper 主持 |
| **博客** | Anthropic Engineering | Anthropic 技术博客 |
| | Claude Blog | Anthropic 官方博客 |

---

## 6. 用户流程 (User Flow)

```
[配置阶段]
用户访问 Settings → 确认/编辑白名单

[后台运行 - 每天 UTC 22:00]
Cron Job 触发
  → POST /api/trigger-fetch → Web Service 后台异步执行
  → 拉取 follow-builders GitHub Feed（x / podcast / blog）
  → 去重过滤（content_id SHA-256 hash）
  → 豆包 API 处理：分类打标 + 双语摘要生成
  → 存入 Supabase PostgreSQL

[用户交互]
用户打开浏览器 → Feed 查看当日摘要 → 分类筛选
                → Archive 查看历史 / 关键词搜索
                → 点击原文链接溯源
```

---

## 7. 技术架构 (Technical Architecture)

### 技术选型

| 层级 | 技术 |
| :--- | :--- |
| 后端语言 | Python 3.11 |
| Web 框架 | FastAPI |
| 前端 | Jinja2 模板 + TailwindCSS CDN + HTMX |
| LLM | 豆包 API（火山引擎 ARK，deepseek-chat） |
| 数据库 | Supabase PostgreSQL（免费套餐，Session Pooler） |
| 定时任务 | Render Cron Job（独立进程，不依赖 Web Service） |
| 数据来源 | follow-builders 公开 GitHub Feed |
| YouTube 转录 | Supadata API（transcript 为空时补充） |
| 部署 | Render（Web Service + 2个 Cron Job） |

### 数据流

```
follow-builders GitHub Feed（每日 UTC 06:00 更新）
  feed-x.json / feed-podcasts.json / feed-blogs.json
    ↓ scrapers/feed_fetcher.py（去重 + Supadata 转录补充）
原始内容存储（raw_content 表）
    ↓ processor/summarizer.py → 豆包 API
结构化摘要存储（summaries 表）
    ↓ routers/ + Jinja2 模板
用户浏览器（Feed / Archive / Settings）
```

---

## 8. 关键约束与假设 (Constraints & Assumptions)

* **数据来源**：依赖 follow-builders 公开 Feed，内容质量和更新频率由该项目决定。
* **内容策略**：不做内容过滤，白名单内所有 Builder 的内容均入库，由用户自行判断价值。
* **LLM 成本**：豆包 API 按 token 计费，每日约 37 条内容，成本极低。
* **Supadata 额度**：免费套餐 100 credits/月，够个人使用（约 30 次/月）。
* **合规性**：摘要生成属"合理使用"，每条内容保留原文链接；不存储完整原文。
* **单用户假设**：无需多租户、权限管理等复杂逻辑。

---

## 9. 成功指标 (Success Metrics)

> 个人工具以"实际使用感受"为主要衡量标准

| 指标 | 目标 |
| :--- | :--- |
| 每日内容准时更新率 | ≥ 95% |
| 摘要双语质量（主观评分） | ≥ 4/5 分 |
| 原文链接有效率 | ≥ 98% |
| Dashboard 页面加载时间 | < 3s |

---

## 10. 路线图 (Roadmap)

### Phase 1 — MVP ✅ 已完成

- [x] follow-builders Feed 抓取（X / Podcast / Blog）
- [x] 豆包 API 摘要生成（双语 + 分类打标）
- [x] Supabase PostgreSQL 数据存储
- [x] FastAPI Web Dashboard（Feed + 分类筛选）
- [x] Render 部署（Web Service + 2个 Cron Job）

### Phase 2 — 深度内容 ✅ 已完成

- [x] Supadata API 接入（YouTube transcript 补充）
- [x] Settings 页白名单管理 UI
- [x] Archive 历史归档页（日期选择 + 关键词搜索）

### Phase 3 — 知识库（待开发）

- [ ] 基于 Builder 历史观点构建 RAG 知识库
- [ ] 支持自然语言提问（如："Karpathy 去年对 RAG 的看法？"）
- [ ] "观点碰撞"专题（两个 Builder 产生讨论时自动聚合）
- [ ] Daily Digest 每日置顶推送
- [ ] Prompt 调优迭代（分类准确率提升、摘要质量优化）
