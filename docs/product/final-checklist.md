# 最终交付 Checklist

更新时间：2026-06-27

## 代码与配置

- [x] 默认向量路线为 SQLite + Python scan/hash fallback，不硬依赖 Chroma、Qdrant 或 sqlite-vec。
- [x] sqlite-vec、Qdrant、Chroma 均作为可选增强，不可用时不影响主链路启动和演示。
- [x] `backend/requirements.txt` 已调整为 LoongArch/Kylin 友好默认依赖：`uvicorn==0.34.0`、`pydantic<2`。
- [x] `.env.example` 不提交 Key，并区分 provider-specific 模型名与 base_url。
- [x] Docker 默认离线启动：mock providers + SQLite vector store + python_scan。
- [x] `git diff --check` 通过。

## 官方主链路

- [x] `/api/multimodal/diagnosis` 已新增并测试。
- [x] 图片诊断结果进入 `queryContext`，失败时 fallback 不返回 500。
- [x] `maintenanceLevel` / `riskLevel` / `deviceType` 已进入 `SearchRequest`、`DiagnosisRequest`、`RagAnswerRequest`。
- [x] RAG 输出包含检修等级说明、作业前准备、作业中风险控制、合规校验提醒。
- [x] RAG 输出保留初步判断、检查步骤、维修步骤、安全提醒、验收标准、引用证据、不确定信息。
- [x] 案例/经验总结字段 `experienceSummary`、`lessonsLearned`、`maintenanceLevel` 已加入。
- [x] 案例/经验默认 `pending_review`，审核通过后可检索，拒绝后不可检索。
- [x] chunk revision 有 revision 记录、审计事件和索引同步。
- [x] approved-only 知识关系网络已测试。
- [x] 图片诊断临时线索不伪装成正式 knowledge evidence。

## 本地验证结果

| 命令 | 结果 |
| --- | --- |
| `.\backend\.venv\Scripts\python.exe -m pytest tests\ -q` | `168 passed in 746.08s` |
| `cd frontend; npm.cmd run build` | 通过；仅有 VueUse pure annotation 和 chunk size warning |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1` | `success=true`，health/provider/search/RAG/审核/知识生命周期通过 |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1` | `success=true`，4 个 JSON 文件健康，未触发恢复 |
| 真实 Qwen LLM 临时环境变量验证 | `remoteOk=true`，`fallback=false`，模型 `xopqwen36v35b`，延迟约 `7539ms` |
| 本地 HTTP API 冒烟 | health/provider/search/RAG/multimodal 均 200；RAG citations 为 4 |
| `git diff --check` | 通过 |

## LoongArch/Kylin 验证结果

- [x] 环境：`loongarch64`，Kylin Linux Advanced Server V11 (Swan25)，Python 3.11.6，Node 20.18.2，Docker 24.0.9。
- [x] 可迁移主测试集：`105 passed in 170.44s`。
- [x] 前端生产构建：`built in 21.41s`，Node 20.18.2 有 Vite 版本 warning，但构建成功。
- [x] `/api/search`、`/api/rag/answer`、`/api/multimodal/diagnosis` 已在 LoongArch/Kylin offline/mock 模式冒烟。
- [x] 目标环境默认依赖路线不使用 `uvicorn[standard]` 和 Pydantic v2 core，避免 LoongArch 上源码编译阻塞。

## 不进入提交包

- `.env`
- API Key
- `.venv`
- `node_modules`
- `frontend/dist`
- `data/uploads` 运行数据（`data/uploads/.gitkeep` 仅为目录占位）
- `data/knowledge`
- 官方 PDF 或来源不明维修手册
- 临时日志、PID、截图、压缩包、运行缓存

## 最终结论

当前建议提交比赛。真实 Qwen 文本 LLM 已用临时环境变量完成本地复验；比赛现场或目标 VM 如果更换 Key、base_url 或模型名，需要重新跑 `/api/providers/llm/validate` 与 `/api/rag/answer`。真实 OCR、真实多模态 provider 仍需按现场环境单独复验；未复验时以 offline/mock 主链路作为稳定演示兜底。
