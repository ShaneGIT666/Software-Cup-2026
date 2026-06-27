# 最终工程测试报告

更新时间：2026-06-27

## 变更范围

- 收口最终交付文档：Checklist、交接说明、agent 启动上下文、官方符合度矩阵、真实 LLM 验证记录。
- 增强 `scripts/loongarch-final-verify.sh`：默认执行系统信息、依赖版本、后端可迁移测试、前端构建、`git diff --check`、已有后端 API 冒烟；`--docker` 模式支持构建、运行、健康检查、日志和清理。
- 未修改核心业务排序算法、RAG prompt、前端协议或数据结构。

## 修改文件

- `docs/product/final-checklist.md`
- `docs/project-management/agent-startup-context.md`
- `docs/project-management/current-handoff.md`
- `docs/project-management/final-engineering-test-report.md`
- `docs/requirements/official-compliance-matrix-final.md`
- `docs/testing/llm-provider-final-validation.md`
- `scripts/loongarch-final-verify.sh`

## 本地后端测试

命令：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\ -q
```

结果：`168 passed in 746.08s (0:12:26)`。

覆盖重点：资料入库、pending_review 隔离、审核状态机、approved-only 检索、RAG、Evidence Pack、维修案例/经验沉淀、人工修正 revision、审计事件、多模态诊断、向量 fallback、评测 runner、JSON 存储恢复。

## 前端构建

命令：

```powershell
cd frontend
npm.cmd run build
```

结果：通过，`built in 4.80s`。

已知 warning：VueUse pure annotation 与 Vite chunk size warning，不阻塞生产构建和比赛演示。

## Readiness

命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
```

结果：`success=true`，耗时约 `934.54ms`。

通过项：health、provider status、async parse task、search seed、RAG answer、case review roundtrip、knowledge chunk lifecycle。

## JSON 存储巡检

命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
```

结果：`success=true`，`fileCount=4`，`issueCount=0`，`repairedCount=0`。

巡检文件：`devices.json`、`manuals.json`、`repair-cases.json`、`workflows.json`。

## 本地 HTTP API 冒烟

方式：启动临时 `uvicorn backend.app.main:app --host 127.0.0.1 --port 18000`，使用 offline/mock 默认配置请求真实 HTTP 接口，完成后关闭进程。

结果：

- `/api/health`：`status=ok`
- `/api/providers/status`：`remoteApiMode=off`，`llm=mock`
- `/api/search`：返回 `4` 条结果
- `/api/rag/answer`：`provider=mock`，返回 `4` 条 citations
- `/api/multimodal/diagnosis`：`queryContext.clueType=inputClue`

## 真实 LLM 验证

方式：仅把 API Key 注入当前 PowerShell 进程环境变量，未写入仓库、文档、日志或 `.env`。

结果：

- `remoteOk=true`
- `provider=openai`
- `model=xopqwen36v35b`
- `apiStyle=chat_completions`
- `fallback=false`
- `latencyMs=7539`
- `contextCount=2`

边界：同一服务的 `/embeddings` 请求返回 `400 Bad Request`，系统已按设计降级为 hash embedding。当前只能宣称真实文本 LLM RAG 已验收，不宣称该服务提供了可用 embedding。

## LoongArch/Kylin

已有目标环境复验记录：

- 系统：LoongArch64 / 银河麒麟 V11。
- 后端可迁移主测试集：`105 passed in 170.44s`。
- 前端生产构建：`built in 21.41s`。
- `/api/search`、`/api/rag/answer`、`/api/multimodal/diagnosis` 已在 offline/mock 模式冒烟。

本轮新增脚本 `scripts/loongarch-final-verify.sh` 已通过 `bash -n` 语法检查。目标 VM 如换包或换环境，应重新运行：

```bash
bash scripts/loongarch-final-verify.sh
bash scripts/loongarch-final-verify.sh --docker
```

## Docker 结果

本轮未重新执行 Docker 构建运行。原因：本轮只修改文档与验证脚本，且本地 Windows 侧不是最终 LoongArch Docker 运行环境；Docker 模式已写入脚本，目标环境应在生成 `frontend/dist` 后执行 `--docker` 并留存日志。

## 离线与 Fallback

- 默认离线配置：`REMOTE_API_MODE=off`、`LLM_PROVIDER=mock`、`MULTIMODAL_PROVIDER=mock`、`OCR_PROVIDER=mock`。
- 默认向量路线：`RAG_VECTOR_STORE=sqlite`、`RAG_VECTOR_SQLITE_ENGINE=python_scan`、`RAG_VECTOR_ENHANCER=off`、`RAG_VECTOR_FALLBACK_LOCAL=on`。
- Chroma、Qdrant、sqlite-vec、真实 OCR、真实多模态均为可选增强，不作为比赛现场主链路硬依赖。

## Approved-only 与审核

已通过测试与 readiness 覆盖：

- 上传资料解析结果默认 `pending_review`。
- `pending_review`、`rejected`、`deprecated`、`replaced` 不参与默认检索。
- 审核通过后进入 `approved`，并进入检索和轻量知识关系网络。
- 人工修正生成 revision 与审计事件。

## 敏感文件与产物

- `git diff --check` 通过。
- 敏感 Key 片段扫描通过，未发现已知 Qwen Key 片段写入仓库。
- 跟踪文件扫描通过，未发现 `.env`、`.venv`、`node_modules`、`frontend/dist`、运行 zip、日志、PID 或运行知识库数据被提交。
- `data/uploads/.gitkeep` 为目录占位文件，可保留。

## 剩余风险

- 目标 VM 若更换网络出口、Key、base_url 或模型名，需要重新跑真实 LLM 验证。
- 真实 OCR/真实多模态 provider 未作为硬依赖；比赛答辩应说明其为可选增强与 fallback 链路。
- 该项目的知识图谱口径是轻量知识关系网络 / 原型，不应宣传为完整工业知识图谱平台。
- `/embeddings` 在当前 Qwen 服务上返回 400，embedding 主张应限定为 hash fallback 或后续接入独立 embedding provider。

## 是否建议提交

建议提交。当前主链路、离线兜底、真实文本 LLM、前端构建、readiness、JSON 巡检和 LoongArch/Kylin 既有复验记录均已形成可解释证据。

## 提交前最后三步

1. 重新确认 `git status --short --branch` 只包含本轮预期文档和脚本变更。
2. 提交并 push 当前收口 commit。
3. 在比赛目标环境运行 `scripts/loongarch-final-verify.sh`，如需 Docker 交付再运行 `scripts/loongarch-final-verify.sh --docker` 并保存日志截图。
