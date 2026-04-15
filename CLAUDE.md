# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**BuilderSignal（匠心信标）** 是一个个人自用的 AI 内容追踪与摘要 Agent。系统自动抓取白名单 AI Builder 在 X (Twitter)、RSS/博客上发布的内容，通过 Claude API 生成双语（中/英）结构化摘要，并在 Web Dashboard 上展示。

**核心设计原则：Track the Builders, Skip the Influencers.**

---

## 规划文档

代码尚未初始化，当前仓库为规划阶段。所有设计决策记录于：

- `PRD.md` — 产品需求文档（功能定义、白名单、路线图）
- `memory-bank/design-document.md` — 产品设计文档（数据库 Schema、页面布局、API 接口、部署方案）
- `memory-bank/tech-stack.md` — 技术栈选型文档（选型理由及被排除方案）

**开始写代码前必须阅读这三份文档。**

---

## 目标架构

```
buildersignal/
├── main.py              # FastAPI 应用入口
├── config.py            # 环境变量读取（python-dotenv）
├── database.py          # SQLAlchemy 连接与 Schema 初始化
├── jobs/
│   ├── fetch.py         # Render Cron Job：抓取 + Claude 处理（每4小时）
│   ├── digest.py        # Render Cron Job：生成每日摘要（每天08:00）
│   └── cleanup.py       # Render Cron Job：清理30天前数据（每天02:00）
├── scrapers/
│   ├── x_scraper.py     # Tweepy 抓取 X 推文
│   ├── rss_scraper.py   # feedparser + httpx 抓取 RSS/博客
│   └── base_scraper.py  # 公共去重逻辑（基于 URL hash）
├── processor/
│   ├── claude_client.py # Claude API 封装，启用 Prompt Caching
│   └── summarizer.py    # 双语摘要生成 + 分类打标
├── routers/
│   ├── feed.py          # GET / 首页
│   ├── archive.py       # GET /archive 历史归档
│   └── settings.py      # GET/POST /settings 配置管理
├── templates/           # Jinja2 模板（含 HTMX 属性）
├── static/              # TailwindCSS CDN 引入，无构建流程
└── data/
    └── buildersignal.db # SQLite 文件（Render Disk 挂载路径）
```

---

## 关键技术决策

**定时任务用 Render Cron Job，不用 APScheduler。**
APScheduler 内嵌于 FastAPI 进程，Render 休眠时定时任务会失效。三个 Cron Job 独立运行在 `jobs/` 目录下的脚本。

**前端用 HTMX，不写 JavaScript。**
分类筛选、局部刷新等交互通过 HTMX 的 HTML 属性实现（`hx-get`, `hx-target`），Jinja2 服务端渲染，无前端构建流程。

**Claude Prompt Caching 必须开启。**
系统提示（分析师角色设定）加 `cache_control: {"type": "ephemeral"}`，批量处理时重复调用成本降低 90%。

**SQLite 存于 Render Disk。**
数据库文件路径通过 `DATABASE_PATH` 环境变量配置，Render 部署时挂载持久化 Disk 到 `/app/data`，否则每次重启数据丢失。

---

## 数据库核心表

| 表名 | 用途 |
| :--- | :--- |
| `builders` | Builder 白名单（内置22人 + 用户自定义） |
| `raw_content` | 原始抓取内容，`content_id` 字段做去重 |
| `summaries` | Claude 处理后的双语摘要，含 `category_tag` |
| `config` | key-value 配置表（推送时间、频率、筛选偏好） |

---

## 环境变量

```
ANTHROPIC_API_KEY      # Claude API
X_BEARER_TOKEN         # X API（Tweepy 只读，Free Tier）
X_API_KEY
X_API_SECRET
X_ACCESS_TOKEN
X_ACCESS_TOKEN_SECRET
DATABASE_PATH          # 默认 ./data/buildersignal.db
TZ                     # 时区，设为 Asia/Shanghai
```

---

## 开发阶段

当前处于 **Phase 1 MVP**，目标是跑通核心链路：

1. FastAPI + SQLite 项目初始化
2. X Scraper（Tweepy）+ RSS Scraper
3. Claude API 摘要处理器（双语 + 分类）
4. Feed 首页（HTMX 分类筛选）
5. Render 部署（Web Service + 3个 Cron Job + Disk）

Phase 2（Archive 页、Settings 页、YouTube 接入）和 Phase 3（RAG 知识库）详见 `PRD.md`。

---

## 重要提示

- 写任何代码前必须完整阅读 `memory-bank/architecture.md`
- 写任何代码前必须完整阅读 `memory-bank/design-document.md`
- 每完成一个重大功能或里程碑后，必须更新 `memory-bank/architecture.md`
