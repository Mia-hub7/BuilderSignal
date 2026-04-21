# BuilderSignal Bug 诊断日志

记录所有线上故障、根本原因、修复方法和预防措施。每次出现异常先查这里。

---

## BUG-003 · 2026-04-21 · Cron Job 无 Disk 挂载，抓取数据写完即丢

**现象**
- Render 面板显示 `buildersignal-fetch: Successful run`，但线上页面无新数据
- `buildersignal-cleanup: Failed run`（每次失败）

**根本原因**
`render.yaml` 中两个 Cron Job（fetch / cleanup）没有配置 `disk` 字段。  
Render 的 Cron Job 每次在全新的临时容器里运行，`/app/data/` 是内存中的临时目录。  
fetch.py 写入的 DB 文件在容器销毁后全部丢失，web service 的持久化 Disk 完全没有被写入。  
cleanup.py 失败是因为临时容器里的 DB 是空的，没有目标表/数据。

**修复**
在 `render.yaml` 中为两个 Cron Job 都加上 `disk` 挂载，引用同一个 `buildersignal-data`：
```yaml
disk:
  name: buildersignal-data
  mountPath: /app/data
```
提交：`render.yaml` → 推送后 Render 自动重新配置服务。

**注意事项**
Render 的 Persistent Disk 通常只允许挂载到单一服务。如果推送后 Render 拒绝多服务共享同一 disk，  
需改为架构方案 B：Cron Job 通过内部 HTTP 调用 web service 的 `/internal/run-fetch` 端点触发处理，  
让 web service 持有 DB 的唯一写入权。

**验证方法**
1. 推送后进 Render Dashboard，检查 fetch Cron Job 下是否出现 Disk 挂载信息
2. 等下一次 fetch job 运行（整点），检查 web 页面数据条数是否增加

---

## BUG-002 · 2026-04-21 · Prompt 代码未提交导致线上持续使用旧版 Prompt

**现象**
- 线上页面筛选 Tab 已是「深度内容 / 观点速览」（新两类）
- 但内容卡片上的标签还是「工具推荐」「产品动态」「行业预判」（旧四类）
- 重新部署后问题依旧，重启也不解决

**根本原因（完整还原）**

| 时间 | 事件 |
|---|---|
| 2026-04-20 10:32 | `045f2ec` 提交了 UI 模板改为两类，但 `processor/claude_client.py` 和 `processor/summarizer.py` 的改动**未包含在这次提交里** |
| 2026-04-20 之后 | Render 部署了新 UI，但 fetch job 跑的还是旧四类 Prompt 代码 |
| 2026-04-21 | 用户发现问题，以为昨天修好了，今天又复现——实际上从未修好过 |
| 2026-04-21 18:57 | `b63371d` 补提交 processor 代码，真正修复 |

**漏掉的文件**
```
processor/claude_client.py   ← V2.1 Prompt（两类分类 + translate 函数）
processor/summarizer.py      ← 调用新的 classify/summarize/translate 拆分接口
```

**修复**
提交 `b63371d`：`fix: deploy V2.1 prompts — 2-class category system + translate for short content`

**预防规则（必须遵守）**
每次修改 Prompt / LLM 相关逻辑后，提交前必须检查：
```bash
git status processor/
```
确认 `processor/` 下没有未提交的改动，再 push。

---

## BUG-001 · 2026-04-20 · 存量数据 category_tag 为旧四类标签

**现象**
UI 改版后，已有数据的标签（工具推荐、技术洞察、产品动态、行业预判）无法匹配新的筛选逻辑。

**根本原因**
历史 summaries 表里的 `category_tag` 字段是旧四类的值，DB 迁移脚本未在部署时自动执行。

**修复**
手动运行一次迁移脚本（需连接到 Render DB 或本地 DB）：
```bash
python scripts/db_migrate_categories.py
```

映射规则：
- 技术洞察 / 产品动态 / 工具推荐 → `深度内容`
- 行业预判 → `观点速览`

迁移结果可用诊断脚本验证：
```bash
python scripts/db_inspect.py
```

**状态**：脚本已写好（`scripts/db_migrate_categories.py`），**尚未在线上 DB 执行**。

---

## 快速排查清单

当线上页面显示异常时，按顺序检查：

```
□ 1. git status processor/       → 有未提交文件？立即提交推送
□ 2. Render Dashboard            → fetch job 最近一次是 Successful 还是 Failed？
□ 3. fetch job 日志              → 写入了几条？还是 skipped？
□ 4. python scripts/db_inspect.py → 数据库里旧标签 / 新标签各多少条？
□ 5. render.yaml                 → cron job 有没有 disk 字段？
```

---

## 架构隐患备忘

| 风险 | 说明 | 当前状态 |
|---|---|---|
| Disk 共享限制 | Render Disk 可能只允许挂载到单一服务，cron job 挂同一 disk 行为待验证 | 已修改 render.yaml，等线上验证 |
| SQLite 并发写 | web service 和 fetch job 同时写 DB 可能导致锁冲突 | 目前 fetch job 运行时间短，冲突概率低；长期建议迁移到 PostgreSQL |
| 数据迁移未自动化 | Prompt 升级时存量数据需手动迁移 | 待解决 |
