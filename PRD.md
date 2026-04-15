# 产品需求文档 (PRD): BuilderSignal (匠心信标)

| 版本 | 状态 | 修订日期 | 负责人 |
| :--- | :--- | :--- | :--- |
| v1.1 | 草案 | 2026-04-15 | AI PM |

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

* **内置白名单**：系统预置约 25 位核心 AI Builder（见第 5 节）。
* **用户自定义扩展**：用户可在 Web Dashboard 中添加白名单以外的任意账号。
* **准入标准参考**：顶级 AI 公司创始人、核心工程师、研究员，或具有公认原创能力的 Builder。
* **验收标准**：用户可在 Dashboard 增删账号，变更实时生效，下次抓取周期自动纳入。

### 4.2 全渠道内容抓取 (Multi-source Ingestion)

| 渠道 | 方案 | MVP 阶段 |
| :--- | :--- | :--- |
| X (Twitter) | 官方 X API Free Tier（月 500 条），后续按需升级 | ✅ |
| 企业/个人博客 | RSS 订阅 + HTTP 爬虫（遵守 robots.txt） | ✅ |
| YouTube / Podcast | Supadata API 转录 | Phase 2 |

* **抓取频率**：每 4 小时扫描一次。
* **去重逻辑**：基于内容 ID 或 URL hash，避免重复推送。

### 4.3 AI 驱动内容处理 (AI Processing)

* **LLM**：Claude API（claude-sonnet-4-6）
* **反网红过滤器**：LLM 自动识别并剔除营销号特征内容（转发抽奖、10图带你看懂等）。
* **分类标签**：每条内容自动打标，支持以下类别过滤：
  * `技术洞察` — 算法、架构、工程实现
  * `产品动态` — 新功能、产品发布、路线图
  * `行业预判` — 对未来趋势的观点与预测
  * `工具推荐` — Builder 提到的工具、库、服务
  * `生活碎碎念` — 非技术内容（默认过滤）
* **结构化摘要（双语）**：
  * **核心观点**（中/英）：Builder 表达了什么新见解？
  * **技术/产品动态**（中/英）：他们正在造什么？
  * **行业预判**（中/英）：对未来的碎片化预测。
  * **原文链接**：每条摘要必须附带原文跳转链接。
* **验收标准**：摘要输出为中英双语，英文为原文提炼，中文为对应翻译，格式为 Markdown。

### 4.4 Web Dashboard

* **技术栈**：Python 后端（FastAPI）+ 轻量前端（HTML/JS 或 Streamlit）
* **核心页面**：
  * **首页 Feed**：按时间倒序展示摘要卡片，支持按类别筛选。
  * **白名单管理**：增删追踪账号，设置每人的关注类别。
  * **推送设置**：配置每日摘要推送时间（默认 08:00）。
  * **历史归档**：按日期浏览历史摘要，支持关键词搜索。
* **验收标准**：可在浏览器中访问，响应时间 < 3s，移动端可阅读。

### 4.5 自动化定时推送 (Scheduled Delivery)

* **推送形式**：每日定时生成 Markdown 摘要报告，在 Web Dashboard 首页置顶展示。
* **推送时间**：用户可在 Dashboard 自定义（精确到小时），默认每日 08:00。
* **推送频率**：支持每日简报（Daily Digest）或每周复盘（Weekly Review）。
* **验收标准**：定时任务准时触发，误差 < 5 分钟；推送失败时记录日志并在下次启动时重试。

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
| | Peter Steinberger | OpenClaw 创始人 |
| | Nan Yu / Madhu Guru | AI Builders |
| | Cat Wu / Thariq | AI Builders |
| | Nikunj Kothari | AI Builder |
| **行业布道与观察** | Swyx (Shawn Wang) | Latent Space |
| | Dan Shipper | Every.to CEO |
| | Peter Yang | AI 产品 Creator |
| | Matt Turck | FirstMark (MAD Landscape) |
| | Aditya Agarwal | 前 Dropbox CTO |
| | Zara Zhang | 前字节跳动产品经理 |

---

## 6. 用户流程 (User Flow)

```
[配置阶段]
用户访问 Dashboard → 确认/编辑白名单 → 设置推送时间与类别偏好

[后台运行 - 每4小时]
定时任务触发
  → 抓取 X API / RSS / 博客内容
  → 去重过滤（基于 URL hash）
  → Claude API 处理：分类打标 + 去噪 + 双语摘要生成
  → 存入数据库（SQLite / PostgreSQL）

[定时推送 - 每日08:00（可配置）]
聚合当日内容 → 生成 Daily Digest Markdown → 更新 Dashboard 首页置顶

[用户交互]
用户打开浏览器 → 查看摘要卡片 → 按类别筛选 → 点击原文链接溯源
```

---

## 7. 技术架构 (Technical Architecture)

### 技术选型

| 层级 | 技术 |
| :--- | :--- |
| 后端语言 | Python 3.11+ |
| Web 框架 | FastAPI |
| 前端 | Jinja2 模板 + TailwindCSS（或 Streamlit 快速原型） |
| LLM | Claude API (claude-sonnet-4-6) |
| 数据库 | SQLite（MVP）→ PostgreSQL（生产） |
| 定时任务 | APScheduler 或 Celery Beat |
| X API | Tweepy（官方 X API Free Tier） |
| YouTube 转录 | Supadata API（Phase 2） |
| 博客抓取 | feedparser（RSS）+ httpx + BeautifulSoup |
| 部署 | Railway / Render / Fly.io |
| 容器化 | Docker + docker-compose |

### 数据流

```
数据源（X / RSS / Blog）
    ↓ 抓取层（Scrapers）
原始内容存储（raw_content 表）
    ↓ 处理层（Claude API）
结构化摘要存储（summaries 表）
    ↓ 展示层（FastAPI + Web UI）
用户 Dashboard
```

---

## 8. 关键约束与假设 (Constraints & Assumptions)

* **X API 限制**：Free Tier 月读取上限 500 条，MVP 阶段够用（25人 × 每4小时 ≈ 150条/天），后续流量增大再升级。
* **合规性**：摘要生成属"合理使用"，每条内容必须保留原文链接；爬虫遵守 robots.txt。
* **语言处理**：LLM 负责将英文原文提炼为双语摘要，无需额外翻译 API。
* **数据质量假设**：Claude 能准确区分 Builder 的"技术观点"与"生活内容"，分类准确率预期 > 85%。
* **单用户假设**：无需多租户、权限管理等复杂逻辑，配置直接写入本地配置文件或环境变量。

---

## 9. 成功指标 (Success Metrics)

> 个人工具以"实际使用感受"为主要衡量标准

| 指标 | 目标 |
| :--- | :--- |
| 每日 Digest 准时生成率 | ≥ 95% |
| 摘要双语质量（主观评分） | ≥ 4/5 分 |
| 反网红过滤准确率 | 营销内容漏出 < 10% |
| 原文链接有效率 | ≥ 98% |
| Dashboard 页面加载时间 | < 3s |

---

## 10. 路线图 (Roadmap)

### Phase 1 — MVP（目标：跑通核心链路）

- [ ] X API 抓取模块（Tweepy）
- [ ] RSS / 博客爬虫模块
- [ ] Claude API 摘要生成（双语 + 分类打标）
- [ ] SQLite 数据存储
- [ ] FastAPI 基础 Web Dashboard（Feed 列表 + 类别筛选）
- [ ] APScheduler 定时任务（每4小时抓取 + 每日推送）
- [ ] Railway/Render 云端部署

### Phase 2 — 深度内容

- [ ] Supadata API 接入（YouTube / Podcast 转录）
- [ ] 白名单管理 UI（Dashboard 内增删账号）
- [ ] 推送时间自定义设置
- [ ] 历史归档与关键词搜索

### Phase 3 — 知识库

- [ ] 基于 Builder 历史观点构建 RAG 知识库
- [ ] 支持自然语言提问（如："Karpathy 去年对 RAG 的看法？"）
- [ ] "观点碰撞"专题（两个 Builder 产生讨论时自动聚合）
