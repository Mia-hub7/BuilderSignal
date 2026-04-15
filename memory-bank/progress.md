# 开发进度记录: BuilderSignal

---

## 已完成

### 步骤 1 — 项目目录结构初始化
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 创建所有目录：`scrapers/`、`processor/`、`jobs/`、`routers/`、`templates/`、`static/css/`、`data/`
- 创建各目录下的 `__init__.py`
- 创建根目录空文件：`main.py`、`config.py`、`database.py`
- 创建 `.env.example`、`.gitignore`、`requirements.txt`（纯 ASCII，兼容 Windows pip）

**遇到的问题：**
- `requirements.txt` 中文注释导致 Windows pip `UnicodeDecodeError (GBK)`，解决：移除所有中文注释

**验证结果：**
- `pip install -r requirements.txt` ✅
- `python -c "import fastapi, sqlalchemy, httpx, bs4, dotenv"` ✅

---

### 步骤 2 — config.py 环境变量加载
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 用 `python-dotenv` 加载 `.env`，暴露模块级常量
- `LLM_API_KEY` 缺失时抛出 `ValueError`，其余项有缺省值

**验证结果：**
- 常量值正确读取 ✅
- 缺少 Key 时抛出明确报错 ✅

---

### 步骤 3 — database.py SQLAlchemy Schema 初始化
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 定义4张表 ORM 模型：`Builder`、`RawContent`、`Summary`、`Config`
- 实现 `init_db()`、`get_session()`

**验证结果：**
- 4张表创建成功，字段与设计文档一致 ✅
- 重复运行不报错 ✅

---

### 步骤 4 — jobs/seed.py Builder 白名单导入
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 写入33条初始记录：25个X账号 + 6个播客 + 2个博客
- 幂等：重复运行不重复插入

**验证结果：**
- 33条记录写入成功 ✅
- 重复运行无重复插入 ✅

---

### 步骤 5 — main.py FastAPI 基础应用启动
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `lifespan` 启动时调用 `init_db()`
- 挂载 `/static`，注册 Jinja2，注册 feed 路由

**遇到的问题：**
- 本机代理拦截 httpx/curl，改用 raw socket 验证

**验证结果：**
- `GET /` 返回 200 OK ✅
- `GET /docs` 正常加载 ✅

---

### 步骤 6 — scrapers/base_scraper.py 去重逻辑
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `generate_content_id()`：SHA-256 hash
- `is_duplicate()`：查询 `raw_content` 表

**验证结果：**
- 同一输入 hash 一致，不同输入不同 ✅
- 插入前 False，插入后 True ✅

---

### 步骤 7 — scrapers/feed_fetcher.py Feed 拉取
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 拉取3个 GitHub raw JSON Feed（x / podcast / blog）
- 去重后写入 `raw_content` 表

**验证结果：**
- 首次运行写入34条新记录（x:32, podcast:1, blog:1）✅
- 重复运行去重生效 ✅

---

### 步骤 8 — processor/claude_client.py LLM API 封装
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 改用豆包（火山引擎 ARK）API，OpenAI SDK 兼容接入
- 实现 `call_llm()`，返回 `{skip, category, summary_zh, summary_en}`
- `httpx.Client(trust_env=False)` 绕过本机代理

**遇到的问题：**
- 本机代理导致 SSL 握手失败，解决：`trust_env=False`

**验证结果：**
- 有价值内容返回摘要 ✅，无价值内容返回 skip:true ✅

---

### 步骤 9 — processor/summarizer.py 摘要生成器
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `run_summarizer()`：每批20条，调用 LLM，写入 summaries 表
- skip=true → is_processed=2，skip=false → is_processed=1

**验证结果：**
- 摘要中英文均不为空 ✅，分类覆盖四类 ✅，failed=0 ✅

---

### 步骤 10 — jobs/fetch.py 完整抓取任务入口
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `run_fetch()`：串联 `fetch_all_feeds()` → `run_summarizer()`
- 每阶段打印带 UTC 时间戳日志

**验证结果：**
- 两阶段顺序完成 ✅，raw_content 34条、summaries 24条 ✅

---

### 步骤 11 — templates/base.html 基础模板
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 引入 TailwindCSS CDN + HTMX CDN
- 顶部固定导航栏：Logo + Feed / Archive / Settings
- 背景色 `#F8FAFC`（冷灰白，科技感）

**验证结果：**
- 导航栏正常显示 ✅，375px 无横向滚动条 ✅

---

### 步骤 12 — Feed 首页
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `routers/feed.py`：查询今日摘要，支持分类过滤
- `templates/feed.html`：标题"今日 AI 动态"、分类 Tab、摘要卡片、空状态
- Tab 用 `<a href>` 全页刷新（HTMX 因代理问题移除）

**遇到的问题：**
- HTMX CDN 被代理拦截，Tab 局部刷新失效；改为全页刷新

**验证结果：**
- 24条摘要正常显示 ✅，Tab 切换高亮正确 ✅，计数更新 ✅

---

### 步骤 13 — 状态接口与手动触发
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `GET /api/status`：返回 last_fetch_time、total/today summaries
- `POST /api/trigger-fetch`：后台异步执行，立即返回 `{"status": "started"}`

**验证结果：**
- 两个接口均返回 200 OK，JSON 格式正确 ✅

---

### 步骤 14 — jobs/cleanup.py 数据清理
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 删除30天前的 summaries 和 raw_content 记录
- 日志格式：`[时间戳] CLEANUP: deleted N summaries, N raw_content`

**验证结果：**
- 旧记录正确删除，近期数据完好 ✅，日志计数准确 ✅

---

### 步骤 15 — Dockerfile + docker-compose.yml
**日期：** 2026-04-15
**状态：** ⏭ 跳过本地验证

**完成内容：**
- `Dockerfile`：python:3.11-slim，安装依赖，暴露8000，uvicorn 启动
- `docker-compose.yml`：挂载 `./data`，注入 `.env`，映射8000端口
- `.dockerignore`：排除 `.env`、`data/`、`__pycache__` 等

**说明：** 本机未安装 Docker，跳过本地验证。Dockerfile 已就绪，Render 部署时直接使用。

---

## 待完成

- [ ] 步骤 16：Render 部署
