# 最终交付 Checklist

## 代码与配置

- [x] 默认向量库为 SQLite，不再硬依赖 Chroma。
- [x] sqlite-vec 可选入口与不可用 fallback 已实现。
- [x] Qdrant 可选增强查询入口与本地 SQLite fallback 已实现。
- [x] Evidence Pack 保留检索诊断和可追溯 citation 字段。
- [x] `.env.example` 不提交 Key，并区分真实 provider 配置。
- [x] Docker 默认可离线启动：mock providers + SQLite vector store。

## 演示主链路

- [x] 上传/解析结果默认 pending_review。
- [x] 审核通过后进入 approved 并同步检索索引。
- [x] 搜索只返回 approved 片段。
- [x] RAG 输出使用标准结构和 citation。
- [x] 真实 LLM 可通过 OpenAI-compatible 配置接入。
- [x] mock/offline 可作为现场兜底。

## 验证命令

本轮提交前执行结果：

| 命令 | 结果 |
| --- | --- |
| `.\backend\.venv\Scripts\python.exe -m pytest tests\ -q` | `159 passed in 638.42s` |
| `cd frontend; npm.cmd run build` | 通过；仅有 VueUse pure annotation 与 chunk size warning |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1` | `success=true`，health/provider/search/RAG/审核/知识生命周期均通过 |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1` | `success=true`，4 个 JSON 文件健康 |
| `git diff --check` | 通过 |

可复验命令：

```powershell
git status --short --branch
.\backend\.venv\Scripts\python.exe -m pytest tests\ -q
cd frontend; npm.cmd run build
powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
git diff --check
```

最终结果以本轮提交前终端输出为准。

## 不进入提交包

- `.env`
- API Key
- `.venv`
- `node_modules`
- `frontend/dist`
- `data/uploads`
- `data/knowledge`
- 临时日志和截图
