# LoongArch / 银河麒麟最终复验说明

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 目标

所有比赛交付能力以 LoongArch/银河麒麟目标环境可运行为准。无法在目标环境稳定运行的增强能力不得作为主链路承诺，应降级为可选或替换技术路线。

## 推荐执行

```bash
bash scripts/loongarch-final-verify.sh
```

脚本只执行本地健康检查、依赖检查、后端测试、前端构建和接口冒烟，不写入 API Key。

## 成功标准

- 后端测试通过。
- 前端构建通过。
- `GET /api/health` 可用。
- `GET /api/providers/status` 可用。
- 检索、RAG、图片诊断、上传审核链路可执行。

## 技术路线约束

- Docker 可用时优先 Docker 部署。
- Docker 不可用时使用 Python venv + FastAPI 静态托管 `frontend/dist`。
- MinerU、OCR、向量增强、视觉模型必须有 fallback。
- 真实 LLM 使用比赛提供的 OpenAI-compatible Qwen 服务。

## 2026-06-26 实测记录

环境：

- CPU 架构：`loongarch64`
- OS：Kylin Linux Advanced Server V11 (Swan25)
- Python：3.11.6
- Node：20.18.2
- Docker：24.0.9

依赖结论：

- `uvicorn[standard]` 会触发 `uvloop/watchfiles/httptools` 等源码构建，不适合作为 LoongArch/Kylin 默认依赖。
- Pydantic v2 的 `pydantic-core` 在该环境会进入源码构建，默认交付路线改为 `pydantic<2`。
- 后端基础依赖使用 `uvicorn==0.34.0` + `pydantic<2`，增强依赖保留为可选。
- 系统初始 Node 有 `node` 但缺 `npm`，已通过 `dnf install npm` 验证可补齐前端构建能力。

已通过：

```text
LoongArch/Kylin 可迁移主测试集：105 passed in 170.44s
前端生产构建：built in 21.41s
GET /api/health：success
GET /api/providers/status：success
POST /api/search：3 条 manual 命中
POST /api/rag/answer：mock fallback，3 条 citations，structuredAnswer 含 complianceChecks
POST /api/multimodal/diagnosis：mock fallback，4 条 citations，maintenanceLevel=emergency
```

未作为失败处理的项：

- `tests/test_motorcycle_manual.py` 依赖 Windows 本地路径 `E:/Download/Downloads/摩托车发动机维修手册.pdf`，目标环境没有该文件，因此不纳入 LoongArch 可迁移主测试集。
- 目标环境 `18000` 端口用于最新代码复验，`8000` 端口已有旧演示服务占用，未强制停止旧服务。
- 本次 VM 冒烟以离线兜底模式运行，真实 Qwen LLM 仍需按 `docs/testing/llm-provider-final-validation.md` 配置 `.env` 后复验。

## 2026-06-27 本轮补强后的复验说明

本轮新增 `/api/rag/feedback` 和更明确的 `multimodalSignals` 返回字段。Windows 本地已完成完整后端测试、前端构建和 HTTP API 冒烟；本轮未重新连接 LoongArch/Kylin VM 执行脚本，因此最终提交前建议在目标环境重新运行：

```bash
bash scripts/loongarch-final-verify.sh
```

如果需要 Docker 交付留证，再运行：

```bash
bash scripts/loongarch-final-verify.sh --docker
```

验收重点：确认 `/api/search`、`/api/rag/answer`、`/api/multimodal/diagnosis`、`/api/rag/feedback` 和 `/api/knowledge/graph` 在 offline/mock 默认链路下均可运行。
