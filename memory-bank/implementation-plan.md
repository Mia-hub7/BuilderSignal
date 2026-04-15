# 实施计划: BuilderSignal

| 版本 | 日期 | 变更 |
| :--- | :--- | :--- |
| v1.0 | 2026-04-15 | 初始版本 |
| v1.1 | 2026-04-15 | 采用 follow-builders 公开 Feed，移除 X API / Tweepy / RSS 自建抓取，移除 digest.py / scheduler.py，头像不做，时区统一 UTC+8 |

> **规则**：严格按顺序执行，每步完成验证后再进入下一步。每步不得包含超出描述范围的功能实现。

---

## 架构说明（v1.1 变更）

BuilderSignal 不自行抓取数据源，而是直接消费 [follow-builders](https://github.com/zarazhangrui/follow-builders) 项目每日发布的公开 Feed。该 Feed 托管于 GitHub，每天 UTC 06:00（北京时间 14:00）自动更新，无需任何 API Key，直接 HTTP 请求即可获取。

**三个 Feed 地址：**
- X 推文：`https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json`
- 播客转录：`https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json`
- 官方博客：`https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json`

**feed-x.json 数据结构：**
```
{
  "generatedAt": "2026-04-14T07:27:54.046Z",
  "lookbackHours": 24,
  "x": [
    {
      "source": "x",
      "name": "Swyx",
      "handle": "swyx",
      "bio": "...",
      "tweets": [
        {
          "id": "...",
          "text": "推文内容",
          "createdAt": "2026-04-13T20:20:14.000Z",
          "url": "https://x.com/swyx/status/...",
          "likes": 527,
          "retweets": 25,
          "replies": 9,
          "isQuote": true
        }
      ]
    }
  ]
}
```

**由此带来的架构简化：**
- 不需要 X API Key、不需要 Tweepy
- 不需要自建 RSS/博客爬虫（博客由 follow-builders 覆盖）
- 不需要 scheduler.py、digest.py
- `scrapers/` 层简化为一个 `feed_fetcher.py`

---

## Phase 1 — MVP

### 里程碑 1：项目骨架

---

#### 步骤 1：初始化项目目录结构

在 `BuilderSignal/` 根目录下创建以下结构：

**目录：**
`scrapers/`、`processor/`、`jobs/`、`routers/`、`templates/`、`static/css/`、`data/`

**空文件：**
每个目录下的 `__init__.py`，以及根目录的 `main.py`、`config.py`、`database.py`

**配置文件：**
- `.env.example`：列出以下4个变量名（值留空）：
  `ANTHROPIC_API_KEY`、`DATABASE_PATH`、`TZ`、`FEED_FETCH_HOUR`
- `.gitignore`：忽略 `.env`、`data/`、`__pycache__/`、`.venv/`
- `requirements.txt`：填入以下所有包及版本（来自 tech-stack.md）：
  ```
  fastapi==0.115.5
  uvicorn[standard]==0.30.6
  jinja2==3.1.4
  python-multipart==0.0.12
  sqlalchemy==2.0.36
  anthropic==0.40.0
  httpx==0.27.2
  beautifulsoup4==4.12.3
  lxml==5.3.0
  python-dotenv==1.0.1
  pydantic==2.9.2
  ```

**验证：**
- 运行 `pip install -r requirements.txt`，确认所有依赖安装成功、无报错
- 运行 `python -c "import fastapi, sqlalchemy, anthropic, httpx, bs4, dotenv"`，确认全部可以正常导入

---

#### 步骤 2：实现环境变量与配置加载（config.py）

在 `config.py` 中实现：
- 用 `python-dotenv` 加载 `.env` 文件
- 读取以下4个配置项为模块级常量：
  - `ANTHROPIC_API_KEY`（必填，缺失时抛出明确错误）
  - `DATABASE_PATH`（缺省值：`./data/buildersignal.db`）
  - `TZ`（缺省值：`Asia/Shanghai`）
  - `FEED_FETCH_HOUR`（缺省值：`15`，即北京时间15:00，对应 follow-builders 每日 UTC 14:00 更新后一小时）

**验证：**
- 复制 `.env.example` 为 `.env`，填入测试用占位值
- 在 Python shell 中 `import config`，打印每个常量，确认值与 `.env` 一致
- 删除 `.env` 中 `ANTHROPIC_API_KEY`，确认程序抛出明确报错而非静默失败

---

#### 步骤 3：初始化数据库与 Schema（database.py）

在 `database.py` 中用 SQLAlchemy 定义以下4张表，字段严格对应 `design-document.md` 第3节：

- `builders`（白名单）
- `raw_content`（原始抓取内容，`content_id` 为唯一键）
- `summaries`（AI 处理后的摘要）
- `config`（key-value 配置表）

同时实现：
- `init_db()`：首次运行时自动建表，已存在则跳过
- `get_session()`：上下文管理器，供其他模块调用

**验证：**
- 直接运行 `python database.py`，确认 `data/buildersignal.db` 文件被创建
- 用 SQLite 客户端（如 DB Browser for SQLite）打开数据库，确认4张表存在，字段与设计文档一致
- 再次运行 `python database.py`，确认不重复建表、不报错

---

#### 步骤 4：导入 Builder 白名单初始数据（jobs/seed.py）

创建 `jobs/seed.py`，将以下25位 Builder 写入 `builders` 表（来源：follow-builders README）：

| handle | name | category |
|---|---|---|
| karpathy | Andrej Karpathy | lab |
| swyx | Swyx | observer |
| joshwoodward | Josh Woodward | lab |
| kevinweil | Kevin Weil | lab |
| petergyang | Peter Yang | observer |
| thenanyu | Nan Yu | builder |
| realmadhuguru | Madhu Guru | builder |
| AmandaAskell | Amanda Askell | lab |
| _catwu | Cat Wu | builder |
| trq212 | Thariq | builder |
| GoogleLabs | Google Labs | lab |
| amasad | Amjad Masad | founder |
| rauchg | Guillermo Rauch | founder |
| alexalbert__ | Alex Albert | lab |
| levie | Aaron Levie | founder |
| ryolu_ | Ryo Lu | builder |
| garrytan | Garry Tan | founder |
| mattturck | Matt Turck | observer |
| zarazhangrui | Zara Zhang | observer |
| nikunj | Nikunj Kothari | builder |
| steipete | Peter Steinberger | builder |
| danshipper | Dan Shipper | observer |
| adityaag | Aditya Agarwal | observer |
| sama | Sam Altman | lab |
| claudeai | Claude | lab |

每条记录设置 `is_default=1`、`is_active=1`、`avatar_url=NULL`（头像功能暂不实现）。

脚本需具备幂等性：以 `handle` 为唯一键，已存在则跳过，不重复插入。

**验证：**
- 运行 `python jobs/seed.py`，查询 `builders` 表，确认25条记录全部存在
- 再次运行，确认记录数仍为25，无重复

---

#### 步骤 5：启动 FastAPI 基础应用（main.py）

在 `main.py` 中：
- 创建 FastAPI 应用实例
- 注册静态文件目录（`/static`）
- 注册 Jinja2 模板引擎（指向 `templates/`）
- 创建临时根路由 `GET /`，返回纯文本 `"BuilderSignal is running"`
- 应用启动时自动调用 `init_db()`

**验证：**
- 运行 `uvicorn main:app --reload`，确认终端无报错
- 浏览器访问 `http://localhost:8000`，确认显示 `BuilderSignal is running`
- 访问 `http://localhost:8000/docs`，确认 FastAPI 自动文档页面正常加载

---

### 里程碑 2：数据采集层

---

#### 步骤 6：实现去重逻辑（scrapers/base_scraper.py）

在 `base_scraper.py` 中实现：
- `generate_content_id(unique_str: str) -> str`：对传入字符串（推文 ID 或文章 URL）做 SHA-256 hash，返回十六进制字符串
- `is_duplicate(content_id: str, session) -> bool`：查询 `raw_content` 表，判断该 `content_id` 是否已存在

**验证：**
- 在 Python shell 中对同一字符串两次调用 `generate_content_id`，确认结果完全相同
- 对两个不同字符串调用，确认结果不同
- 向数据库插入一条 `raw_content` 记录后调用 `is_duplicate`，确认返回 `True`；对未插入的值调用，确认返回 `False`

---

#### 步骤 7：实现 Feed 拉取器（scrapers/feed_fetcher.py）

在 `feed_fetcher.py` 中实现 `fetch_all_feeds()` 函数：

1. 用 `httpx` 依次请求以下3个 URL，获取 JSON 数据：
   - `https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json`
   - `https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json`
   - `https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json`

2. 解析 `feed-x.json`：遍历每个 Builder 的每条推文，提取 `id`、`text`、`url`、`createdAt`、`name`、`handle`，调用 `is_duplicate`（以推文 `id` 为 key），新内容写入 `raw_content` 表，`source` 字段设为 `x`

3. 解析 `feed-podcasts.json`：遍历每个播客条目，提取标题、转录文本、URL、发布时间，调用 `is_duplicate`（以 URL 为 key），新内容写入 `raw_content` 表，`source` 字段设为 `podcast`

4. 解析 `feed-blogs.json`：遍历每篇博客，提取标题、正文、URL、发布时间，调用 `is_duplicate`（以 URL 为 key），新内容写入 `raw_content` 表，`source` 字段设为 `blog`

5. 任意一个 Feed 请求失败时，记录错误日志并继续处理其余两个，不中断整体流程

**验证：**
- 运行 `python scrapers/feed_fetcher.py`，查询 `raw_content` 表，确认有 `source='x'`、`source='podcast'`、`source='blog'` 的记录写入
- 再次运行，确认无重复记录（去重生效）
- 断开网络后运行，确认程序不崩溃，日志中出现错误提示

---

### 里程碑 3：AI 处理层

---

#### 步骤 8：封装 Claude API 客户端（processor/claude_client.py）

在 `claude_client.py` 中实现：
- 初始化 `anthropic.Anthropic` 客户端，从 `config.py` 读取 `ANTHROPIC_API_KEY`
- 实现 `call_claude(builder_name: str, source: str, raw_text: str) -> dict` 函数：
  - 系统提示使用 `design-document.md` 4.3节定义的分析师角色 Prompt
  - 系统提示部分添加 `cache_control: {"type": "ephemeral"}` 启用 Prompt Caching
  - 模型固定为 `claude-sonnet-4-6`
  - 返回解析后的 Python dict（包含 `skip`、`category`、`summary_zh`、`summary_en` 字段）

**验证：**
- 在 `.env` 中填入真实 `ANTHROPIC_API_KEY`
- 在 Python shell 中调用一次 `call_claude`，确认返回包含上述字段的 dict
- 调用第二次，检查响应的 `usage.cache_read_input_tokens` 字段值大于0，确认 Prompt Cache 命中

---

#### 步骤 9：实现摘要生成器（processor/summarizer.py）

在 `summarizer.py` 中实现 `run_summarizer()` 函数：
- 从 `raw_content` 表读取所有 `is_processed=0` 的记录，每批最多20条
- 根据每条记录的 `builder_id` 查询对应的 Builder `name`
- 调用 `call_claude` 传入 `builder_name`、`source`、`raw_text`
- 解析返回结果：
  - `skip=true`：将 `is_processed` 更新为 `2`（已过滤），不写入 `summaries`
  - `skip=false`：将摘要写入 `summaries` 表，`is_processed` 更新为 `1`
- 任意单条失败时记录错误日志并继续，不中断整体流程

**验证：**
- 确保 `raw_content` 表中有 `is_processed=0` 的记录（由步骤7产生）
- 运行 `python processor/summarizer.py`，查询 `summaries` 表，确认有新记录，`summary_zh` 和 `summary_en` 均不为空
- 查询 `raw_content` 表，确认处理后的记录 `is_processed` 已更新为 `1` 或 `2`，不再为 `0`
- 确认至少一条 `category_tag` 属于：技术洞察 / 产品动态 / 行业预判 / 工具推荐

---

#### 步骤 10：实现完整抓取任务入口（jobs/fetch.py）

在 `jobs/fetch.py` 中串联完整流程：
1. 调用 `fetch_all_feeds()`（步骤7）
2. 调用 `run_summarizer()`（步骤9）
3. 每个阶段开始和结束时打印带时间戳的日志（格式：`[2026-04-15 15:00:01] FETCH started`）

**验证：**
- 清空 `raw_content` 和 `summaries` 表（保留 `builders` 数据）
- 运行 `python jobs/fetch.py`，确认日志显示两个阶段均顺序完成
- 查询数据库，确认 `raw_content` 和 `summaries` 均有新数据

---

### 里程碑 4：Web 展示层

---

#### 步骤 11：创建基础 HTML 模板（templates/base.html）

创建 `templates/base.html`，包含：
- 引入 TailwindCSS CDN：`<script src="https://cdn.tailwindcss.com">`
- 引入 HTMX CDN：`<script src="https://unpkg.com/htmx.org@2.0.0">`
- 顶部固定导航栏：Logo "BuilderSignal" + 三个导航链接（Feed / Archive / Settings）
- `{% block content %}` 内容占位区
- 背景白色，最大内容宽度760px，水平居中
- 颜色严格遵循 `design-document.md` 5.5节视觉规范：
  - 主色 `#0F172A`，强调色 `#6366F1`，卡片边框 `#E2E8F0`

**验证：**
- 创建一个继承 `base.html` 的临时测试模板，在 FastAPI 中渲染并访问
- 确认导航栏三个链接可点击
- 在浏览器开发者工具中将视口调至375px宽，确认无横向滚动条

---

#### 步骤 12：实现 Feed 首页（routers/feed.py + templates/feed.html）

实现 Feed 页面：

**路由 `GET /`：**
- 查询 `summaries` 表中 `published_at` 在今日（UTC+8 当天00:00至23:59）范围内的记录
- 支持 `?category=` 参数过滤，无参数时返回全部
- 按 `published_at` 倒序排列

**模板 `feed.html`：**
- 页面顶部显示：当前日期（北京时间格式）和今日内容条数
- 4个分类筛选 Tab（全部 / 技术洞察 / 产品动态 / 行业预判 / 工具推荐），使用 HTMX `hx-get` 和 `hx-target` 属性，点击后只刷新卡片列表区域
- 每条摘要卡片包含：
  - Builder 名字（加粗）+ 来源标记（X / Podcast / Blog）
  - 分类标签（按 `design-document.md` 5.5节颜色规范）
  - 发布时间（相对时间，如"2小时前"）
  - `【EN】` 英文摘要
  - `【中】` 中文摘要
  - 原文链接（底部低调灰色，文字"查看原文"）
- 无数据时显示"今日暂无内容"而非报错

**验证：**
- 访问 `http://localhost:8000`，确认摘要卡片正常渲染
- 点击"技术洞察"Tab，确认 URL 变为 `/?category=技术洞察`，卡片区域刷新，导航栏未重新加载（HTMX 局部刷新生效）
- 清空 `summaries` 表，确认页面显示"今日暂无内容"而非500报错

---

#### 步骤 13：实现状态接口与手动触发（routers/feed.py）

在 `feed.py` 中新增两个接口：

**`GET /api/status`：**
- 返回 JSON：`{"last_fetch_time": "...", "total_summaries": N, "today_summaries": N}`
- `last_fetch_time` 从 `raw_content` 表的最新 `fetched_at` 读取

**`POST /api/trigger-fetch`：**
- 在后台异步执行 `jobs/fetch.py` 的完整流程
- 立即返回 `{"status": "started"}`，不等待完成

**验证：**
- 访问 `http://localhost:8000/docs`，确认两个接口存在
- 调用 `GET /api/status`，确认返回包含三个字段的 JSON
- 调用 `POST /api/trigger-fetch`，确认立即返回 `{"status": "started"}`，后台日志中出现抓取流程输出

---

#### 步骤 14：实现数据清理任务（jobs/cleanup.py）

在 `jobs/cleanup.py` 中实现：
- 删除 `summaries` 表中 `created_at` 早于30天的记录
- 删除 `raw_content` 表中 `fetched_at` 早于30天的记录
- 打印删除的记录数量（格式：`[时间戳] CLEANUP: deleted N summaries, N raw_content`）

**验证：**
- 手动在两张表中各插入一条 `created_at` 为31天前的测试记录
- 运行 `python jobs/cleanup.py`
- 查询数据库，确认旧记录已删除，近期数据完好
- 确认日志中打印的删除数量与实际一致

---

### 里程碑 5：容器化与部署

---

#### 步骤 15：编写 Dockerfile 和 docker-compose.yml

**Dockerfile：**
- 基础镜像：`python:3.11-slim`
- 工作目录：`/app`
- 复制并安装 `requirements.txt`
- 复制全部源码
- 创建 `/app/data` 目录
- 暴露端口8000
- 启动命令：`uvicorn main:app --host 0.0.0.0 --port 8000`

**docker-compose.yml（本地开发用）：**
- 挂载 `./data` 到 `/app/data`（SQLite 持久化）
- 通过 `env_file: .env` 注入环境变量
- 映射本机 8000 端口

**验证：**
- 运行 `docker build -t buildersignal .`，确认构建成功无报错
- 运行 `docker-compose up`，访问 `http://localhost:8000`，确认应用正常响应
- 停止并重启容器，确认 `data/buildersignal.db` 数据持久保留

---

#### 步骤 16：部署至 Render

在 Render Dashboard 按以下顺序操作：

1. 创建 **Web Service**：连接 GitHub 仓库 `Mia-hub7/BuilderSignal`，运行环境选 Docker
2. 在 Environment 页面填入 `ANTHROPIC_API_KEY`、`DATABASE_PATH=/app/data/buildersignal.db`、`TZ=Asia/Shanghai`、`FEED_FETCH_HOUR=15`
3. 创建 **Render Disk**，挂载路径设为 `/app/data`，最小容量
4. 创建 **Cron Job 1**（fetch）：命令 `python jobs/fetch.py`，表达式 `0 7 * * *`（UTC 07:00 = 北京时间 15:00，follow-builders Feed 更新后1小时）
5. 创建 **Cron Job 2**（cleanup）：命令 `python jobs/cleanup.py`，表达式 `0 18 * * *`（UTC 18:00 = 北京时间 02:00）
6. 健康检查 URL 设为 `/api/status`

**验证：**
- Web Service 部署完成后，访问 Render 提供的公网 URL，确认 Feed 页面正常加载
- 访问 `/api/status`，确认返回正常 JSON
- 在 Render Dashboard 手动触发 Cron Job 1，查看日志确认 fetch 流程完成
- 查看 Render Disk，确认 `buildersignal.db` 文件存在

---

## Phase 2 — 完善体验（MVP 上线后执行）

---

#### 步骤 17：实现 Archive 历史归档页

实现 `GET /archive` 路由和 `templates/archive.html`：
- 按日期（UTC+8）分组展示历史摘要，默认显示当月
- 顶部按月份导航（上一月 / 下一月）
- 每天内容默认折叠，点击日期标题展开（HTMX 实现）
- 支持 `?q=关键词` 全文搜索（同时搜索 `summary_zh` 和 `summary_en`）

**验证：**
- 访问 `/archive`，确认历史数据按日期正确分组
- 搜索关键词，确认结果仅显示包含该词的摘要
- 点击日期标题，确认折叠/展开正常

---

#### 步骤 18：实现 Settings 配置页

实现 `GET /settings` 和 `POST /settings/*` 路由及模板：
- 显示当前所有 `is_active=1` 的 Builder 列表，每人有"停用"按钮
- 输入框：支持输入 X Handle 添加自定义 Builder（写入 `builders` 表，`is_default=0`）
- 抓取时间配置（对应 `FEED_FETCH_HOUR`，写入 `config` 表）
- 频率选择（每日 / 每周，写入 `config` 表）
- "立即触发抓取"按钮（调用 `POST /api/trigger-fetch`）

**验证：**
- 停用一个 Builder，重新运行 `fetch.py`，确认该 Builder 的推文不再被写入 `raw_content`
- 添加自定义 Builder，查询 `builders` 表，确认新记录 `is_default=0`
- 修改抓取时间并保存，查询 `config` 表，确认值已更新

---

## 架构更新提醒

每完成一个里程碑后，在 `memory-bank/architecture.md` 末尾追加一行更新记录：日期、版本、主要变更。
