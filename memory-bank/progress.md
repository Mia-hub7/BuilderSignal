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
- 创建 `.env.example`（4个环境变量：`ANTHROPIC_API_KEY`、`DATABASE_PATH`、`TZ`、`FEED_FETCH_HOUR`）
- 创建 `.gitignore`（忽略 `.env`、`data/`、`__pycache__/`、`.venv/`）
- 创建 `requirements.txt`（11个依赖包，移除中文注释以兼容 Windows GBK 编码）

**遇到的问题：**
- `requirements.txt` 中的中文注释导致 Windows 上 pip 报 `UnicodeDecodeError (GBK)`，解决方案：移除所有中文注释，`requirements.txt` 只保留纯 ASCII 内容

---

### 步骤 2 — config.py 环境变量加载
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 用 `python-dotenv` 加载 `.env` 文件
- 暴露4个模块级常量：`ANTHROPIC_API_KEY`、`DATABASE_PATH`、`TZ`、`FEED_FETCH_HOUR`
- `ANTHROPIC_API_KEY` 缺失时主动抛出 `ValueError`，其余三项有缺省值

---

### 步骤 3 — database.py SQLAlchemy Schema 初始化
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 用 SQLAlchemy 2.0 定义4张表的 ORM 模型：`Builder`、`RawContent`、`Summary`、`Config`
- 实现 `init_db()`：首次运行自动建表，已存在则跳过
- 实现 `get_session()`：context manager，自动 commit/rollback/close
- `builders` 表新增 `bio` 字段（2026-04-16），存储 Builder 的公司/身份信息

---

### 步骤 4 — jobs/seed.py Builder 白名单导入
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 写入33条初始记录：25个X账号 + 6个播客节目 + 2个官方博客
- 每个 X 账号补充 `bio` 身份信息（2026-04-16）
- X账号以 `handle` 为唯一键去重，播客/博客以 `name+category` 为唯一键去重
- 脚本幂等：重复运行输出 `0 inserted, 33 skipped`

---

### 步骤 5 — main.py FastAPI 基础应用启动
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 用 `lifespan` 异步上下文管理器在启动时调用 `init_db()`
- 挂载 `/static` 静态文件目录
- 注册 Jinja2 模板引擎（`templates/`）
- 注册 feed_router 和 archive_router

**遇到的问题：**
- 本机有网络代理，httpx/curl 请求被拦截返回 502；改用 raw socket 直连验证

---

### 步骤 6 — scrapers/base_scraper.py 去重逻辑
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `generate_content_id(unique_str)`：SHA-256 hash，返回64位十六进制字符串
- `is_duplicate(content_id, session)`：查询 `raw_content` 表，存在返回 `True`

---

### 步骤 7 — scrapers/feed_fetcher.py follow-builders Feed 拉取
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 拉取3个 GitHub raw JSON Feed（x / podcast / blog）
- X推文以 `tweet.id` 为 content_id，播客以 `guid`，博客以 `url`
- 任意 Feed 失败时记录错误并跳过，不中断整体流程

---

### 步骤 8 — processor/claude_client.py LLM API 封装
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 改用豆包（火山引擎 ARK）API，协议兼容 OpenAI SDK
- 实现 `call_llm(builder_name, source, raw_text) -> dict`
- 传入 `httpx.Client(trust_env=False)` 绕过本机代理

**遇到的问题：**
- 本机代理导致 SSL 握手失败，解决：`trust_env=False`

---

### 步骤 9 — processor/summarizer.py 摘要生成器
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 实现 `run_summarizer()`：每批最多20条，读取 `is_processed=0` 的记录
- `skip=true` 时更新为 2，`skip=false` 时写入 `summaries` 并更新为 1

---

### 步骤 10 — jobs/fetch.py 完整抓取任务入口
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 实现 `run_fetch()`：依次调用 `fetch_all_feeds()` → `run_summarizer()`
- 每阶段打印带 UTC 时间戳的日志

---

### 步骤 11 — templates/base.html 基础模板
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 顶部固定导航栏（Feed / Archive / Settings）
- 导航栏支持当前页高亮（`active_nav` 变量控制）
- TailwindCSS CDN + HTMX CDN 引入

---

### 步骤 12 — Feed 首页
**日期：** 2026-04-15 / 迭代至 2026-04-16
**状态：** ✅ 验证通过

**完成内容：**
- 分类筛选 Tab（全部 / 技术洞察 / 产品动态 / 行业预判 / 工具推荐）
- 卡片展示：平台图标、Builder 名字、身份 bio、分类标签、时间戳、中英摘要、原文链接
- 标题显示当天北京日期
- 今天无数据时自动回退显示最近一次抓取内容（以昨天为优先）
- 今天确实无内容时展示"查看历史资讯"按钮跳转 Archive

**产品设计迭代：**
- 原设计仅显示当天内容，导致早上打开页面为空 → 改为智能回退
- Cron Job 执行时间从 UTC 07:00 改为 UTC 22:00（北京 06:00），确保早上 09:00 有内容

---

### 步骤 13 — 状态接口与手动触发
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- `GET /api/status`：返回最近抓取时间、总摘要数、今日摘要数
- `POST /api/trigger-fetch`：后台异步触发完整抓取任务

---

### 步骤 14 — jobs/cleanup.py 数据清理
**日期：** 2026-04-15
**状态：** ✅ 验证通过

**完成内容：**
- 删除超过30天的 `raw_content` 和 `summaries` 记录
- Render Cron Job 每天 UTC 18:00（北京 02:00）运行

---

### 步骤 15 — Dockerfile + docker-compose.yml
**日期：** 2026-04-15
**状态：** ✅ 验证通过

---

### 步骤 16 — Render 部署
**日期：** 2026-04-16
**状态：** ✅ 完成

**完成内容：**
- Web Service 部署上线：https://buildersignal.onrender.com
- Cron Job `buildersignal-fetch`：每天 UTC 22:00（北京 06:00）运行
- Cron Job `buildersignal-cleanup`：每天 UTC 18:00（北京 02:00）运行
- 新增 `render.yaml` 将部署配置纳入代码管理
- 新增 `.python-version` 锁定 Python 3.11，避免 Render 默认 3.14 导致 pydantic-core 构建失败

---

### Phase 2 — Archive 历史归档页
**日期：** 2026-04-16
**状态：** ✅ 验证通过

**完成内容：**
- `GET /archive`：按日期浏览历史内容
- 日期选择器（数据库中有记录的日期自动生成）
- 分类筛选（与 Feed 一致）
- 卡片展示与 Feed 一致（平台图标、bio、时间戳、摘要、原文链接）

---

### 数据库迁移至 Supabase PostgreSQL
**日期：** 2026-04-16
**状态：** ✅ 完成

**完成内容：**
- Render 免费套餐不支持 Disk，SQLite 每次部署被清空
- 接入 Supabase 免费 PostgreSQL，`DATABASE_URL` 环境变量注入
- `database.py` 支持 `DATABASE_URL` 优先（PostgreSQL），无则回退 SQLite
- 使用 Supabase Session Pooler（port 5432，host: `aws-1-ap-southeast-1.pooler.supabase.com`）
  解决 Render 免费套餐无法连接 Supabase 直连地址（IPv6 不兼容）
- `requirements.txt` 添加 `psycopg2-binary==2.9.9`
- `inspect(engine).get_columns()` 替代 SQLite PRAGMA 做 bio 字段迁移（兼容 PostgreSQL）

---

## 待完成

### Phase 2 — Step 1：Archive 关键词搜索
**日期：** 2026-04-16
**状态：** ✅ 完成

- [x] `archive.py` 增加 `keyword` 查询参数
- [x] SQL 查询加 `summary_zh / summary_en LIKE %keyword%` 条件（`ilike` 兼容 PostgreSQL）
- [x] 搜索时跨所有日期查询，不限单日，最多返回 100 条
- [x] `archive.html` 加搜索框 + 清除按钮，搜索模式下隐藏日期选择器

### Phase 2 — Step 2：Settings 页
**日期：** 2026-04-16
**状态：** ✅ 完成

- [x] `routers/settings.py` 实现 `GET /settings`（展示 builder 列表）
- [x] `POST /settings/builder/add` — 新增 builder，重复时返回错误提示
- [x] `POST /settings/builder/toggle` — 启用/禁用 builder
- [x] `POST /settings/builder/delete` — 删除用户自定义 builder（默认 builder 不可删）
- [x] `templates/settings.html` — 白名单表格 UI，含类别标签、handle、bio
- [x] 操作后显示成功/失败 toast，3秒后自动淡出
- [x] 导航栏 Settings 链接激活

### Phase 2 — Step 3：YouTube / Podcast 转录
**日期：** 2026-04-16
**状态：** ✅ 完成

- [x] 注册 Supadata API，获取 API Key（免费 100 credits/月）
- [x] `scrapers/supadata_client.py` — 封装 Supadata `/youtube/transcript` 接口
- [x] `feed_fetcher.py` — 播客条目 transcript 为空且 URL 为 YouTube 时自动调用转录
- [x] `config.py` 新增 `SUPADATA_API_KEY` 环境变量
- [x] Render 和本地 `.env` 均已配置 API Key

### Phase 3

- [ ] RAG 知识库（基于 Builder 历史观点）
- [ ] 自然语言问答（"Karpathy 去年对 RAG 的看法？"）
- [ ] 观点碰撞专题聚合
