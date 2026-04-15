# 产品设计文档: BuilderSignal (匠心信标)

| 版本 | 状态 | 日期 |
| :--- | :--- | :--- |
| v1.0 | 设计稿 | 2026-04-15 |

---

## 1. 系统概览

### 1.1 系统定位

个人自用的 AI 内容追踪与摘要工具。无需登录，单用户直接访问 Web Dashboard 查看每日推送的 Builder 内容摘要。

### 1.2 核心用户场景

```
每天早上 8:00，系统自动完成以下工作：
  1. 抓取白名单 Builder 在 X / 博客 / RSS 的最新内容
  2. 用 Claude API 过滤噪音、生成双语结构化摘要
  3. 按类别归类，更新 Web Dashboard 首页
用户打开浏览器 → 看到今日摘要卡片 → 按兴趣筛选 → 点击原文溯源
```

### 1.3 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                     Render 云端部署                       │
│                                                         │
│  ┌─────────────┐    ┌──────────────┐   ┌─────────────┐ │
│  │  Scheduler  │───▶│   Scrapers   │──▶│  Processor  │ │
│  │ (APScheduler│    │  X API / RSS │   │ Claude API  │ │
│  │  每4小时)   │    │  Blog Crawler│   │ 摘要+分类   │ │
│  └─────────────┘    └──────────────┘   └──────┬──────┘ │
│                                               │        │
│  ┌─────────────────────────────────────────── ▼──────┐ │
│  │                   SQLite Database                  │ │
│  │     builders / raw_content / summaries / config   │ │
│  └───────────────────────────────┬────────────────────┘ │
│                                  │                      │
│  ┌───────────────────────────────▼────────────────────┐ │
│  │              FastAPI Backend + Jinja2 前端          │ │
│  │         Feed / Filter / Archive / Settings         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                    用户浏览器访问
```

---

## 2. 技术选型

| 层级 | 技术 | 说明 |
| :--- | :--- | :--- |
| 后端框架 | FastAPI | 轻量、异步支持好 |
| 前端 | Jinja2 + TailwindCSS | 无需前后端分离，简洁够用 |
| 数据库 | SQLite | 单用户无需重型数据库 |
| 定时任务 | APScheduler | 内嵌 FastAPI 进程，无需额外服务 |
| LLM | Claude API (claude-sonnet-4-6) | 摘要生成 + 分类 + 双语翻译 |
| X 数据 | Tweepy (X API Free Tier) | 官方 API，月读取上限 500 条 |
| RSS/博客 | feedparser + httpx + BeautifulSoup | 免费，无限制 |
| YouTube (Phase 2) | Supadata API | 语音转文字 |
| 部署 | Render (Free/Starter) | 支持 Docker 部署 |
| 容器 | Docker + docker-compose | 本地开发与生产环境统一 |

---

## 3. 数据库设计

### 3.1 builders 表（Builder 白名单）

```sql
CREATE TABLE builders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- 显示名称，如 "Andrej Karpathy"
    handle      TEXT,                       -- X 账号，如 "karpathy"
    rss_url     TEXT,                       -- RSS/博客地址（可选）
    avatar_url  TEXT,                       -- 头像图片 URL
    category    TEXT,                       -- 所属分类：lab/founder/builder/observer
    is_default  INTEGER DEFAULT 1,          -- 1=内置，0=用户自定义添加
    is_active   INTEGER DEFAULT 1,          -- 1=追踪中，0=已停用
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 raw_content 表（原始抓取内容）

```sql
CREATE TABLE raw_content (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    builder_id   INTEGER REFERENCES builders(id),
    source       TEXT NOT NULL,             -- 来源：x / rss / blog / youtube
    content_id   TEXT UNIQUE,              -- 原始 ID（推文ID、文章URL hash）
    url          TEXT NOT NULL,            -- 原文链接
    raw_text     TEXT,                     -- 原始文本
    published_at DATETIME,                 -- 原文发布时间
    fetched_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_processed INTEGER DEFAULT 0         -- 0=待处理，1=已处理，2=已过滤
);
```

### 3.3 summaries 表（AI 处理后的摘要）

```sql
CREATE TABLE summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_content_id  INTEGER REFERENCES raw_content(id),
    builder_id      INTEGER REFERENCES builders(id),
    category_tag    TEXT,                  -- 技术洞察/产品动态/行业预判/工具推荐
    summary_zh      TEXT,                  -- 中文摘要
    summary_en      TEXT,                  -- 英文摘要
    original_url    TEXT,                  -- 原文链接（冗余存储便于查询）
    published_at    DATETIME,              -- 原文发布时间
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_visible      INTEGER DEFAULT 1      -- 软删除标志
);
```

### 3.4 config 表（用户配置）

```sql
CREATE TABLE config (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
-- 示例数据：
-- digest_time = "08:00"
-- digest_frequency = "daily"  或 "weekly"
-- default_category_filter = "技术洞察,产品动态,行业预判,工具推荐"
```

### 3.5 数据清理策略

- 定时任务每天凌晨 2:00 执行清理
- 删除 `created_at` 超过 30 天的 `summaries` 和 `raw_content` 记录

---

## 4. 后端模块设计

### 4.1 目录结构

```
buildersignal/
├── main.py                  # FastAPI 入口，注册路由，启动 Scheduler
├── config.py                # 环境变量与全局配置读取
├── database.py              # SQLite 连接与初始化
├── scheduler.py             # APScheduler 任务注册
│
├── scrapers/
│   ├── __init__.py
│   ├── x_scraper.py         # Tweepy 抓取 X 推文
│   ├── rss_scraper.py       # feedparser 抓取 RSS/博客
│   └── base_scraper.py      # 公共去重逻辑
│
├── processor/
│   ├── __init__.py
│   ├── claude_client.py     # Claude API 封装（含 Prompt 模板）
│   ├── summarizer.py        # 调用 Claude 生成双语摘要 + 分类
│   └── filter.py            # 反网红过滤规则
│
├── routers/
│   ├── feed.py              # GET /  首页 Feed
│   ├── archive.py           # GET /archive  历史归档
│   └── settings.py          # GET/POST /settings  配置管理
│
├── templates/               # Jinja2 HTML 模板
│   ├── base.html
│   ├── feed.html
│   ├── archive.html
│   └── settings.html
│
├── static/
│   └── css/tailwind.min.css
│
├── data/
│   └── buildersignal.db     # SQLite 数据库文件
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

### 4.2 定时任务设计

```python
# scheduler.py 任务配置

# 任务1：每4小时抓取新内容
@scheduler.scheduled_job('interval', hours=4)
async def fetch_job():
    await run_x_scraper()
    await run_rss_scraper()

# 任务2：每日定时生成 Digest（时间从 config 表读取，默认 08:00）
@scheduler.scheduled_job('cron', hour=8, minute=0)
async def digest_job():
    await generate_daily_digest()

# 任务3：每日凌晨清理过期数据
@scheduler.scheduled_job('cron', hour=2, minute=0)
async def cleanup_job():
    await delete_old_records(days=30)
```

### 4.3 Claude API 调用设计

**Prompt 模板（summarizer）：**

```
系统提示：
你是一个专业的 AI 行业内容分析师。
你的任务是对 AI Builder 发布的内容进行分析和摘要。
只关注有实质价值的内容，忽略营销性、互动性、生活碎碎念类内容。

用户提示：
以下是 {builder_name} 在 {source} 上发布的内容：

{raw_text}

请完成以下任务：
1. 判断这条内容是否值得收录（技术洞察/产品动态/行业预判/工具推荐），
   如果是无价值内容（生活碎碎念、营销互动等），返回 {"skip": true}。
2. 如果值得收录，返回以下 JSON：
{
  "skip": false,
  "category": "技术洞察|产品动态|行业预判|工具推荐",
  "summary_zh": "中文摘要，2-4句，提炼核心观点",
  "summary_en": "English summary, 2-4 sentences, extracting key insights"
}
```

**调用逻辑：**
- 批量处理，每次最多 20 条 raw_content，减少 API 调用次数
- 启用 Claude Prompt Caching（系统提示部分缓存），降低成本

---

## 5. 前端设计

### 5.1 页面结构

```
导航栏（顶部固定）
  Logo: BuilderSignal  |  Feed  |  Archive  |  Settings

页面列表：
  / (Feed)       — 今日摘要主页
  /archive       — 历史归档
  /settings      — 配置管理
```

### 5.2 Feed 页面（主页）

**布局：** 单栏居中，最大宽度 760px，简约白底

**顶部区域：**
```
今日简报 · 2026-04-15          [全部] [技术洞察] [产品动态] [行业预判] [工具推荐]
共 12 条内容
```

**摘要卡片（每条内容）：**

```
┌─────────────────────────────────────────────────────┐
│ 🖼 Andrej Karpathy          技术洞察    2小时前      │
│──────────────────────────────────────────────────── │
│ 【EN】LLMs are not just autocomplete systems...     │
│     Key insight: the emergence of chain-of-thought  │
│     reasoning suggests...                           │
│                                                     │
│ 【中】LLM 不仅仅是自动补全系统...                    │
│     核心观点：思维链推理的涌现表明...                │
│                                                     │
│ → 查看原文 (x.com/karpathy/...)                     │
└─────────────────────────────────────────────────────┘
```

**卡片字段：**
- Builder 头像（圆形，32px）+ 名字（加粗）
- 分类标签（彩色小标签）
- 发布时间（相对时间，如"2小时前"）
- 英文摘要（`【EN】` 前缀）
- 中文摘要（`【中】` 前缀）
- 原文链接（底部，低调灰色）

**分类筛选：**
- 顶部 Tab 切换，默认显示全部
- 筛选状态保留在 URL 参数中（`?category=技术洞察`）

### 5.3 Archive 页面

```
历史归档

[2026-04] [2026-03] ...         按月导航

2026-04-14 (周一) · 8条 ▼
  > Andrej Karpathy · 技术洞察 · LLMs are...
  > Sam Altman · 行业预判 · The next 12 months...

2026-04-13 (周日) · 5条 ▼
  ...
```

- 按日期折叠展示，点击展开当日摘要列表
- 支持关键词搜索（搜索 summary_zh + summary_en）

### 5.4 Settings 页面

**白名单管理：**
```
Builder 追踪列表

[内置 Builder] (22个)
  ✅ Andrej Karpathy   @karpathy    [停用]
  ✅ Sam Altman        @sama        [停用]
  ...

[自定义添加]
  X 账号 Handle：[@___________] 或 RSS URL：[___________]  [+ 添加]
```

**推送配置：**
```
每日摘要推送时间：[08] : [00]   (UTC+8)
推送频率：● 每日  ○ 每周（周一）
```

**操作按钮：**
```
[保存配置]   [立即触发抓取]   [清空今日缓存]
```

### 5.5 视觉规范

| 元素 | 规范 |
| :--- | :--- |
| 字体 | Inter / 系统默认无衬线字体 |
| 主色 | #0F172A（深蓝黑）|
| 强调色 | #6366F1（靛紫）|
| 背景 | #FFFFFF |
| 卡片边框 | #E2E8F0（浅灰）|
| 分类标签色 | 技术洞察:#DBEAFE 产品动态:#D1FAE5 行业预判:#FEF3C7 工具推荐:#F3E8FF |
| 最大内容宽度 | 760px，居中 |

---

## 6. API 接口设计

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| GET | `/` | 首页 Feed，支持 `?category=` 筛选 |
| GET | `/archive` | 历史归档，支持 `?q=关键词&date=2026-04` |
| GET | `/settings` | 设置页面 |
| POST | `/settings/builders` | 添加自定义 Builder |
| DELETE | `/settings/builders/{id}` | 停用 Builder |
| POST | `/settings/config` | 保存推送时间/频率配置 |
| POST | `/api/trigger-fetch` | 手动触发一次抓取 |
| GET | `/api/status` | 返回最近一次抓取时间、条数等状态 |

---

## 7. 环境变量配置

```env
# .env 文件（不提交 Git）

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# X (Twitter) API
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...
X_BEARER_TOKEN=...

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_PATH=./data/buildersignal.db
TZ=Asia/Shanghai
```

---

## 8. 部署方案 (Render)

### 8.1 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.2 Render 配置

| 配置项 | 值 |
| :--- | :--- |
| 服务类型 | Web Service |
| 运行环境 | Docker |
| 实例规格 | Starter ($7/月) 或 Free（有休眠限制） |
| 持久化存储 | Render Disk（挂载 `/app/data`，存放 SQLite 文件）|
| 环境变量 | 在 Render Dashboard 配置 `.env` 中所有变量 |
| 健康检查 | GET `/api/status` |

### 8.3 注意事项

- Render Free 套餐 15 分钟无访问会自动休眠，**定时任务会失效**，建议使用 Starter 套餐
- SQLite 文件存放在 Render Disk（持久化），否则每次重启数据丢失
- 如后续需要更可靠的定时任务，可将 Scheduler 迁移为 Render Cron Job

---

## 9. 开发阶段规划

### Phase 1 — MVP（核心链路跑通）

- [ ] 项目初始化（FastAPI + SQLite + Docker）
- [ ] 数据库 Schema 创建与初始数据导入（Builder 白名单）
- [ ] X Scraper（Tweepy，抓取白名单 Builder 推文）
- [ ] RSS/Blog Scraper（feedparser + BeautifulSoup）
- [ ] Claude API 摘要处理器（双语摘要 + 分类打标）
- [ ] APScheduler 定时任务（每4小时抓取 + 每日08:00 Digest）
- [ ] Feed 首页（卡片展示 + 分类筛选）
- [ ] Render 部署上线

### Phase 2 — 完善体验

- [ ] Archive 历史归档页（含关键词搜索）
- [ ] Settings 页面（白名单管理 + 推送时间配置）
- [ ] YouTube/Podcast 接入（Supadata API）
- [ ] 数据清理定时任务（30天过期删除）

### Phase 3 — 知识库

- [ ] RAG 知识库（基于历史摘要，支持自然语言提问）
- [ ] "观点碰撞"专题（多 Builder 讨论同一话题时自动聚合）

---

## 10. 前置条件清单

在开始开发前，需要准备以下资源：

| 资源 | 获取方式 | 是否必须 |
| :--- | :--- | :--- |
| Anthropic API Key | console.anthropic.com | ✅ MVP |
| X API Credentials | developer.twitter.com 申请 Free Tier | ✅ MVP |
| Render 账号 | render.com 注册 | ✅ 部署 |
| Supadata API Key | supadata.ai 注册 | Phase 2 |
