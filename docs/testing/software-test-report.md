# 软件功能测试报告

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

项目名称：基于多模态大模型技术的设备检修知识检索与作业系统  
版本：0.4
更新时间：2026-06-25

## 1. 测试结论

当前项目已覆盖比赛演示所需的核心链路：检索、资料入库、上传安全、RAG、provider fallback、多模态/OCR mock、MinerU fallback、统一审核、知识片段状态机、审计流水、Chroma 可选召回、评测 runner、JSON 存储恢复、readiness 检查和 LoongArch/Docker 部署验证。

最近确认事实：

1. Windows 本地后端完整测试最新结果：`139 passed in 22.98s`。
2. 前端 `npm.cmd run build` 通过，存在 VueUse pure annotation 和 Vite chunk size warning，不阻塞。
3. `scripts/run-production-readiness-check.ps1` 通过，覆盖 health、provider status、异步解析、检索、RAG、案例审核、知识片段审核和废弃隔离。
4. `scripts/run-json-store-maintenance.ps1` 通过，当前 4 个种子 JSON 文件健康。
5. Qwen / DashScope OpenAI-compatible 文本 RAG 历史小样本真实 API 验收通过；比赛最终模型仍需用最终环境重新验证。
6. LoongArch / 银河麒麟 V11 后端最小依赖和 Docker 一体化部署均已验证；比赛提供环境需按最新提交重新复验并留证。

## 2. 推荐回归命令

后端：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests/ -q
# 139 passed in 22.98s
```

前端：

```powershell
cd frontend
npm.cmd run build
# 通过；Vite chunk size warning 不阻塞
```

本地总体验证：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-verification.ps1
```

准生产 readiness：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
```

JSON 存储巡检：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
```

前端冒烟测试：

```powershell
cd frontend
npm install -D @playwright/test
npm run test:e2e
```

说明：当前环境无法联网安装 `@playwright/test`，因此 E2E 自动执行需在网络可用后补充。

## 3. 后端自动化测试覆盖

| 编号 | 范围 | 说明 |
| --- | --- | --- |
| T-BE-001 | 健康检查 | `/api/health` 返回服务状态 |
| T-BE-002 | Provider 状态 | `/api/providers/status` 返回 LLM、多模态、OCR、embedding 和 fallback 状态 |
| T-BE-003 | 检索 | 正常查询返回 seed 数据、命中词、来源和排序解释 |
| T-BE-004 | 空查询 | 设备型号和故障现象都为空时返回 400 |
| T-BE-005 | RAG mock | mock RAG 返回回答和 citations |
| T-BE-006 | RAG 真实 provider fallback | Key 缺失、离线模式、网络异常时自动 fallback |
| T-BE-007 | LLM validate | OpenAI-compatible `/chat/completions` mock 验收 |
| T-BE-008 | 上传安全 | 空文件、非法扩展名、MIME 不匹配、超大文件均拒绝 |
| T-BE-009 | 资料入库 | TXT/Markdown/PDF/图片等资料生命周期 |
| T-BE-010 | 多模态分析 | 图片/PDF 可进入 mock 多模态分析并生成 chunks |
| T-BE-011 | 多模态 validate | mock、离线跳过、真实 provider mock 成功 |
| T-BE-012 | 知识关系网络 | 生成 device/fault/document/case/workflow 节点和关系 |
| T-BE-013 | Chroma 可选召回 | Chroma 结果合并进 `/api/search` |
| T-BE-014 | embedding provider | `hash`/`openai` 标记进入 `scoreBreakdown.embeddingProvider` |
| T-BE-015 | embedding fallback | 真实 embedding 失败时回退 hash，不影响检索 |
| T-BE-016 | FastAPI 前端托管 | `SERVE_FRONTEND=auto` 时 `/` 返回 SPA，API 不受影响 |
| T-BE-017 | 动态诊断 | `/api/diagnosis` 复用检索/RAG citations，不再返回固定硬编码结果 |
| T-BE-018 | JSON 原子写 | `save_cases()` 等写入先写临时文件再 `os.replace()` |
| T-BE-019 | Chroma 降级 | Chroma 初始化失败或查询失败时返回空召回，不影响主链路 |
| T-BE-020 | 官方 PDF | 官方摩托车维修手册入库、pending_review 审核门槛、审核后检索/RAG/删除/Chroma 流程 |
| T-BE-021 | OCR 可选增强 | mock OCR 文本可生成 pending_review document chunks，审核通过后被检索和 RAG citations 复用 |
| T-BE-022 | OCR fallback | `rapidocr` 等真实 provider 缺失或失败时降级 mock OCR，不影响多模态分析 |
| T-BE-023 | 评测执行器 | 加载 RAG 评测数据集，输出 Hit@K、Recall@K、MRR、违规统计和报告 |
| T-BE-024 | 检索 pipeline | query normalization、metadata filter、RRF、reranker fallback 和 evidence pack |
| T-BE-025 | 知识片段状态机 | `draft/pending_review/approved/rejected/deprecated/replaced` 生命周期和 Chroma 同步 |
| T-BE-026 | 统一审核工作台 | 案例和知识片段 pending_review 审核、拒绝原因、reviewer 和事件记录 |
| T-BE-027 | 审计事件 | review events 记录 before/after，并通过 `/api/review/events` 查询 |
| T-BE-028 | 异步解析任务 | `/api/knowledge/documents/async` 创建任务并进入 pending_review 入库 |
| T-BE-029 | JSON 存储恢复 | 主 JSON 损坏时可从 `.bak` 读取，并提供巡检/修复脚本 |
| T-BE-030 | 系统状态页 | `/api/providers/status` 附带 LLM、Embedding、OCR、MinerU、Chroma、知识统计和 fallback |

## 4. LoongArch / 银河麒麟验证

已验证环境：

```text
Kylin Linux Advanced Server V11 (Swan25)
Python 3.11.6
node 存在
npm/git 不存在
```

已验证内容：

1. 后端最小依赖可安装。
2. 后端测试子集 `39 passed`。
3. Uvicorn 可启动。
4. `/api/health` 正常。
5. `/api/providers/status` 正常。

待复验内容：

1. 上传最新源码和 `frontend/dist`。
2. 设置 `SERVE_FRONTEND=auto`、`FRONTEND_DIST_DIR=../frontend/dist`。
3. 访问 `http://VM:8000/`，确认前端由 FastAPI 返回。

## 5. 已知风险

| 风险 | 影响 | 兜底 |
| --- | --- | --- |
| 真实 API 网络不稳 | RAG 或多模态增强失败 | `REMOTE_API_MODE=off` 强制 mock/local fallback |
| Chroma 在 LoongArch 未验收 | 可选向量增强不可用 | 默认 `RAG_VECTOR_STORE=off`，关键词检索不受影响 |
| hash embedding 非真实语义 | 答辩术语风险 | 文档和返回字段明确标记 `embeddingProvider=hash` |
| 真实多模态 payload 差异 | 不同 provider 兼容性不确定 | 只通过 `/api/providers/multimodal/validate` 做小样本验收 |
| 真实 OCR 依赖兼容性 | RapidOCR/PaddleOCR/Docling/MinerU 等依赖在 LoongArch/Kylin 上未完整验收 | 默认 `OCR_PROVIDER=mock`；真实 OCR 依赖放在 `backend/requirements-ocr.txt` 单独安装验证 |
| 前端 E2E 依赖未安装 | 自动化演示防线不完整 | 网络可用后安装 `@playwright/test` 并执行 |
| JSON 文件并发写 | 多请求写入可能覆盖 | 已改为原子替换降低写坏文件风险；比赛 MVP 低并发可接受，后续可引入文件锁或数据库 |

## 6. 结论

项目已具备比赛演示所需的主要工程闭环。最终提交前仍需在比赛提供环境重新执行部署复验、真实模型 validate、RAG 回答、前端访问和上传审核链路，并保留截图或终端日志。
# 最新测试补充：LoongArch/Kylin Docker 验证（2026-06-06）

本节为最新事实记录，优先级高于下方历史记录。本文必须在不依赖聊天上下文的情况下，让后续 agent、开发者和指导老师理解当前验证状态。

## 验证环境

```text
操作系统：Kylin Linux Advanced Server V11 (Swan25)
CPU 架构：loongarch64
主机名：win000k10481
Docker：24.0.9，服务状态 active
容器基础镜像：cr.loongnix.cn/library/python:3.11
部署方式：本地构建 frontend/dist -> package-demo 打包 -> 上传 VM -> Docker build/run
```

## 验证结论

LoongArch/Kylin VM 上的 Docker 一体化部署已经通过。容器成功构建并运行，FastAPI 后端接口和前端静态页面均可访问。

已验证项目：

1. Docker 镜像构建成功：`software-cup-demo:loongarch`。
2. Docker 容器启动成功：`software-cup-demo Up`。
3. `GET /api/health` 返回 `success=true`。
4. `GET /api/providers/status` 返回离线兜底 provider 状态。
5. `GET /` 返回前端 HTML，开头包含 `<!doctype html>` 和 `lang="zh-CN"`。

关键输出：

```json
{"success":true,"data":{"status":"ok","version":"0.1.0"},"message":""}
```

```html
<!doctype html>
<html lang="zh-CN">
```

## 本轮暴露并修复的问题

1. `uvicorn[standard]` 会触发 `httptools` 原生构建，在 LoongArch 容器中失败；Dockerfile 已改为容器内使用 `uvicorn==0.34.0`。
2. Pydantic 2 会触发 `pydantic-core` 原生构建，在 LoongArch 容器中失败；Dockerfile 已追加 `pydantic<2` 容器运行时约束。
3. Uvicorn 在 LoongArch 容器内注册 signal handler 时出现 `OSError: [Errno 22] Invalid argument`；Dockerfile 已改为清空 `uvicorn.server.HANDLED_SIGNALS` 后启动。
4. `HEAD /` 对当前 SPA fallback 返回 405；验证脚本已改为 `GET / | head -c 160`。

## 当前风险边界

Docker 验证默认采用离线兜底配置：

```env
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
RAG_VECTOR_STORE=off
```

这说明 Docker 部署链路、前后端一体化访问、Mock/RAG 兜底链路已经可用于比赛演示。真实 API、Chroma、真实多模态仍属于增强能力，应在网络、Key 和依赖可控时单独验收。
## 最新测试补充：MinerU 接入验证（2026-06-09）

本次补充验证 MinerU 已从“预留接口”推进为文档解析主链路：

1. 后端虚拟环境已安装 `mineru[all]==3.2.3`，CLI 返回 `mineru, version 3.2.3`。
2. DOCX 小样本已通过项目 `parse_document()` 链路解析，返回 `parser=mineru`、`status=parsed`、`fallback=False`。
3. `parser_router` 对 PDF / DOCX / PPTX / XLSX 优先调用 MinerU；失败、超时、未安装或关闭时自动 fallback。
4. MinerU 解析结果保存 `raw_parse_result.json`、`parsed.md`、`assets/`。
5. 解析生成的知识片段默认 `review_status=pending_review`，审核通过前不参与正式 RAG 检索和 Chroma 同步。

最新回归命令与结果：

```powershell
$env:MINERU_ENABLED="false"
.\backend\.venv\Scripts\python.exe -m pytest tests -q
# 139 passed in 22.98s

cd frontend
npm.cmd run build
# passed, only existing VueUse pure annotation and Vite chunk size warning
```

详细部署说明见：`docs/deployment/mineru-document-parsing.md`。
