# 实施计划: BuilderSignal

| 版本 | 日期 |
| :--- | :--- |
| v1.0 | 2026-04-15 |

> **规则**：严格按顺序执行，每步完成验证后再进入下一步。每步不得包含超出描述范围的功能实现。

---

## Phase 1 — MVP

### 里程碑 1：项目骨架

---

#### 步骤 1：初始化项目目录结构

在 `BuilderSignal/` 根目录下，按照 `architecture.md` 中定义的结构创建所有文件夹和空文件：
- 创建目录：`scrapers/`、`processor/`、`jobs/`、`routers/`、`templates/`、`static/css/`、`data/`
- 创建空文件：每个目录下的 `__init__.py`，以及 `main.py`、`config.py`、`database.py`、`scheduler.py`
- 创建 `.env.example`，列出 `ANTHROPIC_API_KEY`、`X_BEARER_TOKEN`、`X_API_KEY`、`X_API_SECRET`、`X_ACCESS_TOKEN`、`X_ACCESS_TOKEN_SECRET`、`DATABASE_PATH`、`TZ` 共8个变量名（值留空）
- 创建 `.gitignore`，忽略 `.env`、`data/`、`__pycache__/`、`.venv/`
- 创建 `requirements.txt`，列入 `tech-stack.md` 依赖清单中的所有包及版本

**验证：**
- 运行 `pip install -r requirements.txt`，确认所有依赖安装成功、无报错
- 运行 `python -c "import fastapi, sqlalchemy, anthropic, tweepy, feedparser, httpx, bs4, dotenv"`，确认全部可以正常导入

---

#### 步骤 2：实现环境变量与配置加载（config.py）

在 `config.py` 中实现配置加载逻辑：
- 用 `python-dotenv` 加载 `.env` 文件
- 将8个环境变量读取为模块级常量
- `DATABASE_PATH` 缺省值为 `./data/buildersignal.db`
- `TZ` 缺省值为 `Asia/Shanghai`

**验证：**
- 复制 `.env.example` 为 `.env`，填入测试用占位值（不需要真实 API Key）
- 在 Python shell 中 `import config`，打印每个常量，确认值与 `.env` 一致
- 删除 `.env` 中某个变量，确认程序抛出明确的缺失提示而非静默失败

---

#### 步骤 3：初始化数据库与 Schema（database.py）

在 `database.py` 中完成：
- 用 SQLAlchemy 定义 `builders`、`raw_content`、`summaries`、`config` 四张表，字段严格对应 `design-document.md` 第3节的 SQL 定义
- 实现 `init_db()` 函数：首次运行时自动建表，已存在则跳过
- 实现 `get_session()` 上下文管理器，供其他模块调用

**验证：**
- 直接运行 `python database.py`，确认 `data/buildersignal.db` 文件被创建
- 用 SQLite 客户端（如 DB Browser for SQLite）打开数据库，确认四张表存在且字段名、类型与设计文档完全一致
- 再次运行 `python database.py`，确认不会重复建表、不会报错

---

#### 步骤 4：导入 Builder 白名单初始数据

创建 `jobs/seed.py`，将 `PRD.md` 第5节中的22位 Builder 以硬编码方式写入 `builders` 表：
- 每条记录包含：`name`、`handle`（X 账号）、`category`（lab/founder/builder/observer）、`is_default=1`、`is_active=1`
- 脚本需具备幂等性：若记录已存在（以 `handle` 为唯一键判断），则跳过而非重复插入

**验证：**
- 运行 `python jobs/seed.py`，用 SQLite 客户端查询 `builders` 表，确认22条记录全部存在
- 再次运行 `python jobs/seed.py`，确认记录数仍为22，无重复

---

#### 步骤 5：启动 FastAPI 基础应用（main.py）

在 `main.py` 中完成：
- 创建 FastAPI 应用实例
- 注册静态文件目录（`/static`）
- 注册 Jinja2 模板引擎（指向 `templates/`）
- 创建一个临时根路由 `GET /`，返回纯文本 `"BuilderSignal is running"`
- 应用启动时自动调用 `init_db()`

**验证：**
- 运行 `uvicorn main:app --reload`，确认终端无报错
- 浏览器访问 `http://localhost:8000`，确认页面显示 `BuilderSignal is running`
- 访问 `http://localhost:8000/docs`，确认 FastAPI 自动文档页面正常加载

---

### 里程碑 2：数据采集层

---

#### 步骤 6：实现去重基础逻辑（scrapers/base_scraper.py）

在 `base_scraper.py` 中实现：
- `generate_content_id(url: str) -> str`：对 URL 做 SHA-256 hash，返回十六进制字符串
- `is_duplicate(content_id: str, session) -> bool`：查询 `raw_content` 表，判断该 `content_id` 是否已存在

**验证：**
- 在 Python shell 中导入函数，对同一个 URL 两次调用 `generate_content_id`，确认两次结果完全相同
- 对两个不同 URL 调用，确认结果不同
- 向数据库插入一条 `raw_content` 记录后，调用 `is_duplicate`，确认返回 `True`；对未插入的 URL 调用，确认返回 `False`

---

#### 步骤 7：实现 RSS/博客抓取器（scrapers/rss_scraper.py）

在 `rss_scraper.py` 中实现：
- 从 `builders` 表读取所有 `is_active=1` 且 `rss_url` 不为空的 Builder
- 用 `feedparser` 解析每个 RSS 源，提取最新条目的：标题、正文摘要、发布时间、原文 URL
- 调用 `is_duplicate` 去重，新内容写入 `raw_content` 表，`source` 字段设为 `rss`
- 用 `httpx.AsyncClient` 并发请求多个 RSS 源（非串行）

**验证：**
- 在 `builders` 表中手动插入一条带有公开有效 RSS URL 的测试 Builder（例如 Anthropic 官方博客）
- 运行 `rss_scraper.py`，查询 `raw_content` 表，确认有新记录写入且 `source='rss'`
- 再次运行，确认无重复记录产生（去重生效）

---

#### 步骤 8：实现 X 推文抓取器（scrapers/x_scraper.py）

在 `x_scraper.py` 中实现：
- 用 Tweepy 的 `Client`（Bearer Token 认证）初始化只读连接
- 从 `builders` 表读取所有 `is_active=1` 且 `handle` 不为空的 Builder
- 对每个 Builder 抓取过去24小时内的推文，每人最多取10条
- 遇到 Rate Limit（429）时，记录日志并跳过该 Builder，不中断整体流程
- 新推文写入 `raw_content` 表，`source` 字段设为 `x`，`content_id` 使用推文原始 ID

**验证：**
- 在 `.env` 中填入真实 X API credentials
- 运行 `x_scraper.py`，查询 `raw_content` 表，确认有 `source='x'` 的记录写入
- 确认 `url` 字段为可访问的推文链接格式（`https://x.com/{handle}/status/{id}`）
- 再次运行，确认无重复记录

---

### 里程碑 3：AI 处理层

---

#### 步骤 9：封装 Claude API 客户端（processor/claude_client.py）

在 `claude_client.py` 中实现：
- 初始化 `anthropic.Anthropic` 客户端，从 `config.py` 读取 API Key
- 实现 `call_claude(user_prompt: str) -> str` 函数：
  - 系统提示使用 `design-document.md` 4.3节定义的分析师 Prompt
  - 系统提示部分添加 `cache_control: {"type": "ephemeral"}` 启用 Prompt Caching
  - 模型固定为 `claude-sonnet-4-6`
  - 返回模型的文本响应内容

**验证：**
- 在 `.env` 中填入真实 Anthropic API Key
- 在 Python shell 中调用 `call_claude("test content")`，确认能返回字符串响应
- 检查 API 响应头中的 `cache_read_input_tokens`，第二次调用时确认该值大于0（缓存命中）

---

#### 步骤 10：实现摘要生成器（processor/summarizer.py）

在 `summarizer.py` 中实现：
- 从 `raw_content` 表读取所有 `is_processed=0` 的记录，每批最多20条
- 对每条记录调用 `call_claude`，将原始文本、Builder 名字、来源平台传入 Prompt
- 解析 Claude 返回的 JSON：
  - 若 `skip=true`，将该记录的 `is_processed` 更新为 `2`（已过滤），不写入 summaries
  - 若 `skip=false`，将摘要写入 `summaries` 表，并将 `is_processed` 更新为 `1`
- 任意单条记录处理失败时，记录错误日志并继续处理下一条，不中断整体流程

**验证：**
- 确保 `raw_content` 表中已有若干 `is_processed=0` 的测试记录（由步骤7、8产生）
- 运行 `summarizer.py`，查询 `summaries` 表，确认有新记录，且 `summary_zh` 和 `summary_en` 均不为空
- 查询 `raw_content` 表，确认所有已处理记录的 `is_processed` 已更新为 `1` 或 `2`，不再为 `0`
- 确认至少有一条 `category_tag` 值属于：技术洞察 / 产品动态 / 行业预判 / 工具推荐 之一

---

#### 步骤 11：实现完整抓取任务入口（jobs/fetch.py）

在 `fetch.py` 中将步骤7、8、10串联为一个完整流程：
1. 运行 RSS Scraper
2. 运行 X Scraper
3. 运行 Summarizer（处理本次新增的 raw_content）
4. 每个阶段开始和结束时打印带时间戳的日志

**验证：**
- 清空 `raw_content` 和 `summaries` 表（保留 `builders` 数据）
- 运行 `python jobs/fetch.py`，确认终端日志显示三个阶段均顺序完成
- 查询数据库，确认 `raw_content` 和 `summaries` 均有新数据写入

---

### 里程碑 4：Web 展示层

---

#### 步骤 12：创建基础 HTML 模板（templates/base.html）

创建 `templates/base.html`，包含：
- 引入 TailwindCSS CDN（`<script src="https://cdn.tailwindcss.com">`）
- 引入 HTMX CDN（`<script src="https://unpkg.com/htmx.org@2.0.0">`）
- 顶部固定导航栏：Logo "BuilderSignal" + 三个导航链接（Feed / Archive / Settings）
- 定义 `{% block content %}` 内容占位区
- 整体背景白色，最大内容宽度 760px，水平居中
- 颜色严格遵循 `design-document.md` 5.5节视觉规范

**验证：**
- 创建一个继承 `base.html` 的测试模板，在 FastAPI 中渲染并访问
- 确认导航栏三个链接均可点击（暂时跳转到 `#`）
- 在移动端宽度（375px）下检查页面可正常阅读、无横向溢出

---

#### 步骤 13：实现 Feed 首页（routers/feed.py + templates/feed.html）

实现 Feed 页面：
- 路由 `GET /`：从 `summaries` 表查询今日数据，按 `published_at` 倒序排列
- 支持 `?category=` 查询参数过滤，无参数时返回全部
- 每条摘要以卡片形式渲染，卡片包含：Builder 名字、分类标签（带颜色）、发布时间（相对时间，如"2小时前"）、英文摘要（`【EN】` 前缀）、中文摘要（`【中】` 前缀）、原文链接
- 页面顶部显示4个分类筛选 Tab，每个 Tab 使用 HTMX 的 `hx-get` 和 `hx-target` 属性，点击后只刷新卡片列表区域，不整页跳转
- 页面顶部显示当前日期和今日内容条数

**验证：**
- 访问 `http://localhost:8000`，确认页面正常渲染，显示数据库中已有的摘要卡片
- 点击"技术洞察"Tab，确认 URL 变为 `/?category=技术洞察`，卡片列表刷新，且导航栏未重新加载（HTMX 局部刷新生效）
- 数据库无数据时，确认页面显示"暂无内容"提示而非报错

---

#### 步骤 14：实现手动触发接口（routers/feed.py）

在 `feed.py` 中新增：
- `POST /api/trigger-fetch`：手动触发一次完整的 `fetch.py` 流程（后台异步执行）
- `GET /api/status`：返回 JSON，包含最近一次抓取时间和抓取条数（从数据库读取）

**验证：**
- 访问 `http://localhost:8000/docs`，找到两个新接口
- 调用 `POST /api/trigger-fetch`，确认返回成功响应，后台日志中出现抓取流程输出
- 调用 `GET /api/status`，确认返回的 JSON 包含 `last_fetch_time` 和 `total_count` 字段

---

#### 步骤 15：实现数据清理任务（jobs/cleanup.py）

在 `cleanup.py` 中实现：
- 删除 `summaries` 表中 `created_at` 早于30天的记录
- 删除 `raw_content` 表中 `fetched_at` 早于30天的记录
- 打印删除的记录数量日志

**验证：**
- 手动在 `summaries` 和 `raw_content` 表中插入两条 `created_at` 为31天前的测试记录
- 运行 `python jobs/cleanup.py`
- 查询数据库，确认这两条旧记录已被删除，近期数据未受影响
- 日志中打印的删除数量与实际一致

---

### 里程碑 5：容器化与部署

---

#### 步骤 16：编写 Dockerfile

按照 `design-document.md` 8.1节编写 `Dockerfile`：
- 基础镜像：`python:3.11-slim`
- 工作目录：`/app`
- 复制并安装 `requirements.txt`
- 复制全部源码
- 创建 `/app/data` 目录
- 暴露端口 8000
- 启动命令：`uvicorn main:app --host 0.0.0.0 --port 8000`

同时编写 `docker-compose.yml` 用于本地开发：
- 挂载 `./data` 到容器的 `/app/data`（数据持久化）
- 挂载 `.env` 文件注入环境变量
- 映射本机 8000 端口

**验证：**
- 运行 `docker build -t buildersignal .`，确认镜像构建成功、无报错
- 运行 `docker-compose up`，访问 `http://localhost:8000`，确认应用正常响应
- 停止并重启容器，确认 `data/buildersignal.db` 中的数据持久保留

---

#### 步骤 17：部署至 Render

按照 `design-document.md` 8.2节在 Render Dashboard 完成配置：

1. 创建 **Web Service**，连接 GitHub 仓库，运行环境选 Docker，启动命令为 `uvicorn main:app --host 0.0.0.0 --port 8000`
2. 在 Web Service 的 Environment 页面，填入 `.env.example` 中全部8个环境变量的真实值
3. 创建 **Render Disk**，挂载路径设为 `/app/data`，容量选最小规格
4. 创建 **Cron Job 1**（fetch）：命令 `python jobs/fetch.py`，表达式 `0 */4 * * *`
5. 创建 **Cron Job 2**（digest）：命令 `python jobs/digest.py`，表达式 `0 8 * * *`（UTC+8 需换算为 UTC 0:00）
6. 创建 **Cron Job 3**（cleanup）：命令 `python jobs/cleanup.py`，表达式 `0 2 * * *`（UTC+8 需换算为 UTC 18:00 前一天）
7. 健康检查 URL 设为 `/api/status`

**验证：**
- Web Service 部署完成后，访问 Render 提供的公网 URL，确认 Feed 页面正常加载
- 访问 `/api/status`，确认返回正常 JSON（Render 健康检查通过）
- 在 Render Dashboard 手动触发一次 Cron Job 1（fetch），查看日志确认抓取流程运行成功
- 查看 Render Disk 挂载状态，确认 `buildersignal.db` 文件存在

---

## Phase 2 — 完善体验（MVP 上线后执行）

---

#### 步骤 18：实现 Archive 历史归档页

实现 `GET /archive` 路由和 `templates/archive.html`：
- 按日期分组展示历史摘要，默认显示当月
- 顶部按月份导航（上一月 / 下一月）
- 每天的内容默认折叠，点击日期标题展开
- 支持 `?q=关键词` 全文搜索（同时搜索 `summary_zh` 和 `summary_en`）

**验证：**
- 访问 `/archive`，确认历史数据按日期正确分组展示
- 在搜索框输入关键词，确认结果仅显示包含该词的摘要
- 点击日期标题，确认折叠/展开交互正常（通过 HTMX 实现）

---

#### 步骤 19：实现 Settings 配置页

实现 `GET /settings` 和 `POST /settings/*` 路由及对应模板：
- 显示当前所有 `is_active=1` 的 Builder 列表，每人有"停用"按钮
- 提供输入框：输入 X Handle 或 RSS URL 添加自定义 Builder
- 推送时间选择器（小时 + 分钟）和频率选择（每日/每周）
- 保存后更新 `config` 表
- 提供"立即触发抓取"按钮（调用 `/api/trigger-fetch`）

**验证：**
- 停用一个 Builder，重新运行 `fetch.py`，确认该 Builder 的内容不再被抓取
- 添加一个自定义 Builder（X Handle），查询 `builders` 表，确认新记录 `is_default=0`
- 修改推送时间并保存，查询 `config` 表，确认 `digest_time` 值已更新

---

#### 步骤 20：接入 Supadata API（YouTube 转录）

在 `scrapers/` 下新建 `youtube_scraper.py`：
- 从 `builders` 表读取有关联 YouTube 频道的 Builder
- 调用 Supadata API 获取最新视频的转录文本
- 新内容写入 `raw_content` 表，`source` 字段设为 `youtube`
- 在 `jobs/fetch.py` 中将此步骤加入流程

**验证：**
- 配置 Supadata API Key 后运行 `fetch.py`
- 查询 `raw_content` 表，确认存在 `source='youtube'` 的记录
- 查询 `summaries` 表，确认对应摘要已生成

---

## 架构更新提醒

每完成一个里程碑后，在 `memory-bank/architecture.md` 末尾的"架构更新记录"表中追加一行，记录：日期、版本号、主要变更内容。
