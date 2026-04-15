# 技术栈文档: BuilderSignal

| 版本 | 日期 |
| :--- | :--- |
| v1.0 | 2026-04-15 |

---

## 选型原则

> 单用户个人工具，优先**简单可维护**，其次**健壮可靠**，不过度设计。

---

## 完整技术栈一览

| 层级 | 选型 | 版本 | 说明 |
| :--- | :--- | :--- | :--- |
| 后端框架 | FastAPI | 0.115+ | 轻量异步，内置数据验证 |
| 前端模板 | Jinja2 | 3.1+ | 服务端渲染，无需前端构建工具 |
| 前端交互 | HTMX | 2.0+ | 无需写 JS 即可实现动态筛选 |
| CSS | TailwindCSS CDN | 3.x | 直接引入 CDN，零构建配置 |
| 数据库 | SQLite | 内置 | 单用户足够，零运维 |
| ORM | SQLAlchemy | 2.0+ | 简洁的数据库操作，方便后续迁移 |
| 定时任务 | Render Cron Job | — | 独立进程，比 APScheduler 更健壮 |
| LLM | Claude API | claude-sonnet-4-6 | 摘要 + 分类 + 双语 |
| Anthropic SDK | anthropic | 0.40+ | 官方 Python SDK，支持 Prompt Cache |
| X 数据抓取 | Tweepy | 4.14+ | 官方 X API Python 封装 |
| RSS 解析 | feedparser | 6.0+ | 成熟稳定，零依赖 |
| HTTP 客户端 | httpx | 0.27+ | 异步支持，替代 requests |
| HTML 解析 | BeautifulSoup4 | 4.12+ | 博客正文提取 |
| 环境变量 | python-dotenv | 1.0+ | 本地开发读取 .env |
| 数据验证 | Pydantic | 2.0+ | FastAPI 内置，无需额外安装 |
| 服务器 | Uvicorn | 0.30+ | ASGI 服务器，FastAPI 标配 |
| 容器 | Docker | 24+ | 本地与生产环境一致 |
| 部署平台 | Render | — | Web Service + Cron Job + Disk |

---

## 各层详细说明

### 1. 后端：FastAPI + Uvicorn

**为什么选 FastAPI：**
- 比 Flask 更现代，原生异步，适合 I/O 密集型的抓取任务
- 内置 Pydantic 数据验证，API 接口自带类型检查
- 自动生成 `/docs` 接口文档，调试方便

**为什么不用 Flask：**
- 缺乏原生异步支持，多个 scraper 并发时性能差

---

### 2. 前端：Jinja2 + HTMX + TailwindCSS CDN

**为什么选 Jinja2 服务端渲染：**
- 无需 Node.js / npm / 构建流程，单 Python 项目即可运行
- 个人工具不需要 React/Vue 的复杂度

**为什么加 HTMX：**
- 实现分类筛选、按需加载等动态交互，无需手写 JavaScript
- 一行 HTML 属性即可完成 AJAX 请求，极大降低前端复杂度

```html
<!-- 示例：点击分类标签，仅刷新卡片区域，无整页跳转 -->
<button hx-get="/?category=技术洞察" hx-target="#feed-list" hx-push-url="true">
  技术洞察
</button>
```

**为什么选 TailwindCSS CDN：**
- 直接在 HTML 中引入一行 CDN，零配置
- 个人工具不需要 PostCSS 构建流程

---

### 3. 数据库：SQLite + SQLAlchemy

**为什么选 SQLite：**
- 单用户场景，无并发写入压力，SQLite 完全够用
- 零运维，数据库就是一个文件，备份简单

**为什么用 SQLAlchemy（而非裸 SQL）：**
- 代码更清晰，防止 SQL 注入
- 未来如需迁移到 PostgreSQL，只需改连接字符串

**Render 上的注意事项：**
- SQLite 文件必须挂载 **Render Disk**（持久化存储），否则每次部署重启数据丢失
- Render Disk 最低 $1/月，必须开启

---

### 4. 定时任务：Render Cron Job（替代 APScheduler）

**为什么不用 APScheduler：**
- APScheduler 运行在 FastAPI 同一进程内，Web 服务崩溃则定时任务一起挂
- Render 的 Free 套餐 15 分钟无访问会休眠，APScheduler 会随之停止

**为什么选 Render Cron Job：**
- 独立进程，与 Web Service 完全解耦
- 即使 Web 服务重启，定时任务不受影响
- 配置简单，在 Render Dashboard 填写 cron 表达式即可

**任务拆分方式：**

```
Render Web Service   → FastAPI 处理页面请求 + 手动触发抓取
Render Cron Job 1    → 每4小时运行 python jobs/fetch.py（抓取 + 处理）
Render Cron Job 2    → 每天08:00运行 python jobs/digest.py（生成每日摘要）
Render Cron Job 3    → 每天02:00运行 python jobs/cleanup.py（清理过期数据）
```

---

### 5. LLM：Claude API + Prompt Caching

**模型选择：** `claude-sonnet-4-6`
- 摘要质量高，速度快，成本适中
- 支持 Prompt Caching，系统提示命中缓存后成本降低 90%

**Prompt Caching 使用方式：**

```python
# 系统提示加 cache_control，重复调用时节省 token 费用
response = client.messages.create(
    model="claude-sonnet-4-6",
    system=[
        {
            "type": "text",
            "text": "你是专业的 AI 行业内容分析师...",
            "cache_control": {"type": "ephemeral"}  # 启用缓存
        }
    ],
    messages=[{"role": "user", "content": raw_text}]
)
```

---

### 6. X 数据抓取：Tweepy（X API Free Tier）

**限制说明：**
- Free Tier：每月 500 条推文读取
- 25 个 Builder × 每天平均 2 条 = 50 条/天 → 月消耗约 1,500 条

**应对策略（MVP 阶段）：**
- 优先抓取过去 24 小时内的推文（减少重复读取）
- 遇到 Rate Limit 时，自动等待并在下次周期重试
- 后续如超出限制，升级至 Basic 套餐（$100/月）

---

### 7. RSS / 博客抓取：feedparser + httpx + BeautifulSoup4

- **feedparser**：解析标准 RSS/Atom，覆盖大多数技术博客
- **httpx**：异步 HTTP 请求，多个 RSS 源并发抓取
- **BeautifulSoup4**：针对无 RSS 的博客（如 Anthropic Engineering），直接解析 HTML 正文

---

## 依赖清单（requirements.txt）

```txt
# Web 框架
fastapi==0.115.5
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.12

# 数据库
sqlalchemy==2.0.36

# LLM
anthropic==0.40.0

# X API
tweepy==4.14.0

# 数据抓取
feedparser==6.0.11
httpx==0.27.2
beautifulsoup4==4.12.3
lxml==5.3.0

# 工具
python-dotenv==1.0.1
pydantic==2.9.2
```

---

## 项目运行结构（对应 Render 配置）

```
buildersignal/
├── main.py              # FastAPI 应用（Web Service 入口）
├── jobs/
│   ├── fetch.py         # Cron Job 1：抓取 + Claude 处理
│   ├── digest.py        # Cron Job 2：生成每日摘要
│   └── cleanup.py       # Cron Job 3：清理过期数据
├── ...
```

**Render 服务配置：**

| 服务名 | 类型 | 启动命令 | 触发时间 |
| :--- | :--- | :--- | :--- |
| buildersignal-web | Web Service | `uvicorn main:app --host 0.0.0.0 --port 8000` | 常驻 |
| buildersignal-fetch | Cron Job | `python jobs/fetch.py` | `0 */4 * * *` |
| buildersignal-digest | Cron Job | `python jobs/digest.py` | `0 8 * * *` |
| buildersignal-cleanup | Cron Job | `python jobs/cleanup.py` | `0 2 * * *` |

---

## 被排除的方案

| 方案 | 排除原因 |
| :--- | :--- |
| Flask | 缺原生异步，抓取并发差 |
| Django | 太重，单用户工具杀鸡用牛刀 |
| Streamlit | 无法精细控制 UI 布局，不适合 Feed 样式 |
| React / Vue | 个人工具无需前后端分离，增加构建复杂度 |
| PostgreSQL | 单用户无并发需求，SQLite 足够 |
| APScheduler | 与 Web 进程耦合，Render 休眠会导致任务失效 |
| Celery | 需要 Redis，引入额外服务，过度设计 |
| requests | 不支持异步，改用 httpx |
