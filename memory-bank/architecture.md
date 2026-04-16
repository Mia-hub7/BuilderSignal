
# 系统架构文档: BuilderSignal

| 版本 | 日期 | 变更 |
| :--- | :--- | :--- |
| v1.0 | 2026-04-15 | 初始架构（基于步骤1完成后的项目骨架） |

---

## 1. 整体架构

BuilderSignal 由三个独立运行的部分组成，均部署在 Render 上：

```
┌──────────────────────────────────────────────────────────────┐
│                        Render 云端                            │
│                                                              │
│  ┌─────────────────┐   ┌──────────────────────────────────┐  │
│  │  Web Service    │   │         Cron Jobs (2个)           │  │
│  │  FastAPI        │   │  fetch.py    → 每天UTC 07:00      │  │
│  │  用户访问 Dashboard  │  cleanup.py  → 每天UTC 18:00      │  │
│  └────────┬────────┘   └──────────────┬───────────────────┘  │
│           │                           │                      │
│           └──────────┬────────────────┘                      │
│                      ▼                                       │
│            ┌─────────────────┐                               │
│            │  SQLite + Disk  │                               │
│            │  (持久化存储)    │                               │
│            └─────────────────┘                               │
└──────────────────────────────────────────────────────────────┘
          ▲                        ▲
    用户浏览器              follow-builders 公开 Feed
                        (GitHub raw JSON，每天UTC 06:00更新)
```

**关键原则：**
- Web Service 与 Cron Job 完全解耦
- 不自建数据抓取，直接消费 follow-builders 公开 Feed
- 无需任何第三方 API Key（X API / YouTube API 等）

---

## 2. 数据流

```
follow-builders GitHub Feed（每日UTC 06:00更新）
  feed-x.json        ──┐
  feed-podcasts.json ──┼──▶  scrapers/feed_fetcher.py
  feed-blogs.json    ──┘              │
                                      │ 去重（content_id hash）
                                      ▼
                               raw_content 表
                                      │
                                      ▼
                            processor/summarizer.py
                            → claude_client.py
                            → Claude API (claude-sonnet-4-6)
                            → Prompt Caching 启用
                                      │
                                      ▼
                               summaries 表
                          (category_tag + summary_zh + summary_en)
                                      │
                                      ▼
                             routers/ + templates/
                             Jinja2 + HTMX 渲染
                                      │
                                      ▼
                                用户浏览器
```

---

## 3. 文件结构与各文件职责

```
BuilderSignal/
├── main.py              # FastAPI 应用入口：注册路由、挂载静态文件、启动时调用 init_db()
├── config.py            # 环境变量加载：读取 .env，暴露4个全局常量供其他模块 import
├── database.py          # SQLAlchemy：定义4张表的 ORM 模型，提供 init_db() 和 get_session()
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py  # 去重工具函数：generate_content_id() + is_duplicate()
│   └── feed_fetcher.py  # 拉取 follow-builders 的3个 JSON Feed，解析后写入 raw_content 表
│
├── processor/
│   ├── __init__.py
│   ├── claude_client.py # Claude API 封装：call_claude()，启用 Prompt Caching，返回解析后的 dict
│   └── summarizer.py    # 批量读取 raw_content(is_processed=0)，调用 Claude，写入 summaries 表
│
├── jobs/
│   ├── __init__.py
│   ├── seed.py          # 一次性脚本：向 builders 表写入33条初始数据（25个X账号+6个播客+2个博客）
│   ├── fetch.py         # Cron Job 入口：依次调用 feed_fetcher → summarizer，含时间戳日志
│   └── cleanup.py       # Cron Job 入口：删除超过30天的 raw_content 和 summaries 记录
│
├── routers/
│   ├── __init__.py
│   ├── feed.py          # GET / (首页Feed) + GET /api/status + POST /api/trigger-fetch
│   ├── archive.py       # GET /archive（历史归档，Phase 2）
│   └── settings.py      # GET/POST /settings（配置管理，Phase 2）
│
├── templates/           # Jinja2 HTML 模板（服务端渲染，含 HTMX 属性）
│   ├── base.html        # 导航栏、CDN引入、{% block content %} 占位
│   ├── feed.html        # 首页摘要卡片 + 分类筛选 Tab
│   ├── archive.html     # 历史归档（Phase 2）
│   └── settings.html    # 配置管理（Phase 2）
│
├── static/
│   └── css/             # 预留静态资源目录（TailwindCSS 使用 CDN，此目录暂为空）
│
├── data/
│   └── buildersignal.db # SQLite 数据库文件（Render Disk 挂载路径，git 忽略）
│
├── memory-bank/         # 项目规划与进度文档（非运行代码）
├── Dockerfile           # 生产镜像（python:3.11-slim）
├── docker-compose.yml   # 本地开发环境（挂载 data/ 和 .env）
├── requirements.txt     # Python 依赖（纯 ASCII，兼容 Windows pip）
├── .env.example         # 环境变量模板（4个变量）
├── .env                 # 实际环境变量（git 忽略，不提交）
├── .gitignore
├── CLAUDE.md            # AI 开发助手指引
└── PRD.md               # 产品需求文档
```

---

## 4. 数据库结构

```
builders（33条初始数据）
  ├── 25个 X 账号（category: lab/founder/builder/observer）
  ├── 6个 播客节目（category: podcast，handle=NULL）
  └── 2个 官方博客（category: blog，handle=NULL）
         │
         ├──▶ raw_content    去重 key: content_id (SHA-256 hash)
         │         │          is_processed: 0=待处理 1=已处理 2=已过滤
         │         │
         │         └──▶ summaries   category_tag / summary_zh / summary_en
         │
config（key-value）
  digest_time / digest_frequency / default_category_filter
```

---

## 5. 外部依赖

| 服务 | 用途 | 费用 | 备注 |
| :--- | :--- | :--- | :--- |
| follow-builders Feed | 原始内容来源（X/播客/博客） | 免费 | GitHub raw，每日UTC 06:00更新 |
| Claude API (claude-sonnet-4-6) | 双语摘要 + 分类打标 | 按token计费 | Prompt Cache 可降低90%成本 |
| Render Web Service | 托管 FastAPI 应用 | Starter $7/月 | Free套餐会休眠，影响Cron Job |
| Render Disk | SQLite 文件持久化 | $1/月起 | 挂载至 /app/data |
| Render Cron Job | 定时触发 fetch/cleanup | 免费 | 独立进程，不依赖Web Service |

---

## 6. 关键设计决策

| 决策 | 原因 |
| :--- | :--- |
| 使用 follow-builders 公开 Feed | 无需 X API Key，零成本获取25个Builder的推文 |
| Render Cron Job 替代 APScheduler | 独立进程，Render休眠不影响定时任务 |
| HTMX 替代 React/Vue | 个人工具，服务端渲染够用，无需构建流程 |
| SQLite 替代 PostgreSQL | 单用户无并发写入，零运维 |
| Prompt Caching | 系统提示重复调用，缓存命中率高，降低API成本 |
| requirements.txt 不含中文注释 | Windows pip 默认GBK编码，中文注释导致UnicodeDecodeError |

---

## 7. 架构更新记录

| 日期 | 版本 | 变更内容 |
| :--- | :--- | :--- |
| 2026-04-15 | v1.0 | 初始架构，完成项目骨架（步骤1），确立 follow-builders Feed 方案 |
