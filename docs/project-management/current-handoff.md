# 当前开发交接说明

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

更新时间：2026-06-27
历史适用对象：当时的 Coding Agent、协作者和人工复审人员。
现行优先级：本文不再是开发入口；后续修改必须先读根 README、`docs/change-log/INDEX.md` 及相关模块最新记录。
历史文档规范：以下内容按当时交接语境保留，不得用于覆盖当前状态、需求或开发流程。

## 1. 当前状态

项目目标仍是完成中国软件杯 A1 赛题“基于多模态大模型技术的设备检修知识检索与作业系统”。当前主线不是生产级重构，而是比赛作品收口：可部署、可演示、可解释、可兜底、可抗追问。

最终主链路：

```text
设备型号 / 故障描述 / 故障图片 / 检修等级
-> OCR / 多模态分析线索
-> approved-only 检索
-> RRF
-> Evidence Pack
-> LLM / mock 结构化作业指引
-> 案例 / 经验沉淀
-> pending_review 审核
-> approved 后进入检索和轻量知识关系网络
```

最终验证快照：

1. Windows 本地主线后端全量测试：`174 passed in 729.77s`。
2. Windows 前端生产构建通过；仅有 VueUse pure annotation 和 Vite chunk size warning，不阻塞演示。
3. readiness 检查通过：health/provider/search/RAG/审核/知识生命周期均通过。
4. JSON 存储巡检通过：4 个 JSON 文件健康，未触发恢复。
5. LoongArch / 银河麒麟 V11 可迁移主测试集：`105 passed in 170.44s`。
6. LoongArch / 银河麒麟 V11 前端生产构建：`built in 21.41s`。
7. LoongArch / 银河麒麟 V11 offline/mock 模式已完成 `/api/search`、`/api/rag/answer`、`/api/multimodal/diagnosis` 冒烟。
8. 真实 Qwen 文本 LLM 已用临时环境变量完成本地复验：`remoteOk=true`、`fallback=false`、模型 `xopqwen36v35b`、延迟约 `7539ms`；仓库不提交 API Key。
9. 真实 OCR/多模态 provider 不作为主链路硬依赖；sqlite-vec/Qdrant/Chroma 为可选增强；hash embedding 是 fallback。
10. 知识图谱口径为“轻量知识关系网络 / 知识图谱原型”，默认 approved-only。

已确认事实：

1. Windows 本地主线后端测试最新结果为 `174 passed in 729.77s`，覆盖 pending_review 审核门槛、资料入库、RAG、上传安全、多模态/OCR mock、跨模态信号、RAG feedback、向量 fallback、评测 runner、状态机、审计事件和存储恢复。
2. 前端 `npm.cmd run build` 已通过；存在 VueUse pure annotation 和 Vite chunk size warning，不阻塞比赛演示。
3. 准生产 readiness 检查和 JSON 存储巡检已通过。
4. Qwen / DashScope OpenAI-compatible 文本 RAG 已通过本地临时环境变量验收；如果比赛现场更换 Key、base_url 或模型名，仍需在目标环境执行 `/api/providers/llm/validate` 与 `/api/rag/answer` 复验。
5. LoongArch / 银河麒麟 V11 虚拟机已完成最新主链路复验：可迁移主测试集 `105 passed in 170.44s`，前端构建 `built in 21.41s`，search/RAG/multimodal diagnosis 离线冒烟通过。
6. 目标 VM 默认依赖路线为 `uvicorn==0.34.0` + `pydantic<2`；不要把 `uvicorn[standard]` 或 Pydantic v2 core 作为 LoongArch/Kylin 硬依赖。
7. 官方样例 PDF `E:/Download/Downloads/摩托车发动机维修手册.pdf` 只作为本地测试/演示输入，不得提交进 Git。
8. OCR 已作为可选增强接入：`OCR_PROVIDER=mock` 默认兜底，`rapidocr`/`tesseract` 可选；OCR 识别文本会生成 `pending_review` 资料 chunks，审核通过前不进入正式检索、RAG citations、Chroma 或知识关系网络。

## 2. 已实现能力

后端：

1. `POST /api/search`：approved-only 检索，关键词/可选向量召回经 RRF 排序，返回 `matchedTerms`、`reason`、`scoreBreakdown`。
2. `POST /api/diagnosis`：复用检索/RAG 管道生成结构化诊断，返回可能原因、排查动作、安全提醒和 citations，不再是固定硬编码结果。
3. `POST /api/rag/answer`：基于 Evidence Pack 生成结构化 RAG 作业指引，支持 mock/openai/anthropic、citations、上下文裁剪、token 控制和 fallback；输出包含 `complianceChecks`。
4. `POST /api/multimodal/diagnosis`：支持设备型号、故障描述、故障图片、检修等级和风险等级；OCR/多模态线索只进入 query context，不绕过审核成为正式 evidence。
5. `POST /api/providers/llm/validate`：真实文本 LLM 小样本验收，只读取服务端环境变量，不接收前端 Key。
6. `GET /api/providers/status`：返回 LLM、多模态、OCR、embedding、reranker、系统知识统计、MinerU、Chroma 和离线兜底状态。
7. `POST /api/knowledge/documents` / `/api/knowledge/documents/async`：资料同步或异步入库，支持 `pdf/txt/md/docx/pptx/xlsx/jpg/jpeg/png/webp`；PDF/DOCX/PPTX/XLSX 优先走 MinerU，生成片段默认 `pending_review`。
8. `POST /api/knowledge/documents/{document_id}/analyze`：对 PDF/图片资料做多模态分析和可选 OCR，并生成 `pending_review` chunks。
9. `POST /api/providers/multimodal/validate`：真实多模态小样本验收入口，失败不影响主链路。
10. `POST /api/cases` / `POST /api/cases/{case_id}/review`：维修案例、经验总结、教训复盘以 `pending_review` 进入审核，通过后同步为可检索知识。
11. `POST /api/knowledge/graph`：轻量知识关系网络原型，默认 approved-only。
12. Chroma 可选向量索引：`RAG_VECTOR_STORE=chroma` 时启用；未安装、关闭、初始化失败或查询失败时会降级为空召回。
13. FastAPI 可选托管前端：`SERVE_FRONTEND=auto` 且 `frontend/dist/index.html` 存在时，`/` 返回 SPA 页面。
14. JSON 持久化已使用临时文件 + `os.replace()` 原子替换，支持 `.bak` 恢复和离线巡检/修复脚本。
15. `GET /api/review/items` / `/api/review/events`：统一审核工作台和审核流水查询。

前端：

1. 工业检修指挥台风格 Web GUI。
2. 检索、结果证据、作业流程、资料入库、多模态分析、RAG 建议、知识关系网络、案例提交/审核和审计流水的演示闭环。
3. Provider 状态提示与 fallback 文案。
4. Playwright 冒烟测试文件已新增，覆盖首页、检索、结果和 RAG 提示；依赖需联网安装后运行。

脚本：

1. `start-dev.bat`：本地开发一键启动。
2. `scripts/run-backend-tests.ps1`：后端测试。
3. `scripts/run-local-verification.ps1`：本地总体验证。
4. `scripts/configure-api.ps1` / `configure-api.bat`：API 配置，含 Qwen、DeepSeek、SiliconFlow 预设。
5. `scripts/build-frontend.ps1`：构建 `frontend/dist`。
6. `scripts/package-demo.ps1`：准备可上传到 LoongArch 的演示包。
7. `scripts/run-frontend-smoke.ps1`：运行前端 Playwright 冒烟测试。
8. `scripts/run-production-readiness-check.ps1`：离线准生产链路检查。
9. `scripts/run-json-store-maintenance.ps1`：JSON 存储巡检/修复。

## 3. 关键配置

本地兜底：

```env
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
RAG_VECTOR_STORE=off
```

Qwen / DashScope 文本 RAG：

```env
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_API_STYLE=chat_completions
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
OPENAI_API_KEY=your-key
```

Chroma 可选增强：

```env
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=hash
```

真实 embedding 可选增强：

```env
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_API_STYLE=openai_compatible
```

LoongArch 前端托管：

```env
SERVE_FRONTEND=auto
FRONTEND_DIST_DIR=../frontend/dist
```

OCR 可选增强：

```env
OCR_PROVIDER=mock
OCR_LANG=ch
```

真实 OCR 依赖放在 `backend/requirements-ocr.txt`，默认后端依赖仍保持最小部署链路。

## 4. 风险边界

必须准确表述：

1. Chroma 已接入为可选向量索引增强，但 hash embedding 是 fallback/占位，不是生产级语义 embedding。
2. 真实文本 RAG 已用 Qwen 小样本验收；真实多模态 API 目前只有验收接口，是否可用取决于 provider、模型、网络和 payload 支持。
3. 多模态 mock 能保证比赛演示不断链，但不能宣称等同生产级 OCR/视觉诊断。
4. 轻量知识关系网络是知识沉淀展示原型，不是完整图数据库或 GraphRAG。
5. 资料片段已有统一审核工作台、状态机、人工修正 revision 和审计事件；代码层面已保证未审核片段不参与正式检索。
6. OCR provider 是可选增强；RapidOCR、PaddleOCR、Docling、MinerU 等真实依赖需要单独记录安装命令、样本效果、许可证和 LoongArch/Kylin 风险。
7. LoongArch 后端最小依赖与 Docker 一体化部署已验证；前端完整浏览器访问仍需按 FastAPI 静态托管方案在最终环境保留复验证据。
8. 不提交 `.env`、官方 PDF、`data/uploads/`、`data/knowledge/`、`frontend/dist/`、`node_modules/`、`.venv/`。

## 5. 推荐下一步

1. 使用比赛提供环境和最终模型配置复验真实 LLM，至少保留一次 `fallback=false` 的 RAG 回答证据；本地已验证 `xopqwen36v35b` 可用。
2. 在目标环境上传最新 release 包，验证 `/`、`/api/health`、`/api/providers/status`、`/api/search`、`/api/rag/answer` 和上传审核链路。
3. 整理最终产品说明书、演示 runbook、PPT 大纲和 7 分钟视频脚本。
4. 扩充评测样例并保存最终评测报告，明确真实模型结果与 fallback 结果。
5. 如要展示真实多模态，只用一张小图片做 `POST /api/providers/multimodal/validate`，不要一次上传整本 PDF 消耗 token。

## 6. 接手规则

1. 开始前执行 `git status --short --branch`。
2. 不使用 `git reset --hard` 或 `git checkout --` 回滚协作者改动。
3. 当时曾要求 API、数据状态、演示路径和风险边界变化同步更新本文；现行变更改为记录到 `docs/change-log/` 并更新 `INDEX.md`。
4. 新增重依赖前先说明 LoongArch 风险，并保留 mock/offline 兜底。
# Docker 部署入口（2026-06-06 最新）

Docker 方案当时作为 LoongArch / Kylin V11 验证辅助路径。该阅读优先级已经失效；如需复用相关脚本，应先按现行 README 核对 Docker 状态并重新验证。

当前 Docker 路线的边界如下：

1. Docker 默认使用离线兜底配置：`REMOTE_API_MODE=off`、`LLM_PROVIDER=mock`、`MULTIMODAL_PROVIDER=mock`、`RAG_VECTOR_STORE=off`。
2. VM 没有 `git/npm`，因此远程部署脚本优先通过 `curl` 下载 GitHub zip，不依赖 `git clone`。
3. 如果 GitHub 源码包不包含 `frontend/dist`，脚本会显式失败并提示使用包含 dist 的 GitHub Release/Artifact zip；不应在 VM 上临时安装 npm 来绕过该问题。
4. 脚本不会保存 sudo 密码；如果 `sudo -n docker info` 不可用，需先在 VM 终端手动完成 Docker 预处理。
5. Docker 是比赛演示和部署验证辅助方案，不替代原生 LoongArch/Kylin 运行验证要求。
# 最新交接补充：Docker 验证已完成（2026-06-06）

LoongArch / Kylin V11 Docker 一体化部署在 2026-06-06 的原型版本上曾完成验证。该结论不覆盖后续 Dockerfile、配置和 API 变更；当前 Docker 路径仍按 README 标记为历史资料和待重新验收项。

已确认：

1. VM 架构为 `loongarch64`，Docker 服务为 `active`。
2. `software-cup-demo:loongarch` 镜像构建成功。
3. `software-cup-demo` 容器启动成功。
4. `/api/health`、`/api/providers/status` 和 `/` 均已验证通过。
5. Dockerfile 已针对 LoongArch 容器适配：`uvicorn==0.34.0`、`pydantic<2`、兼容 uvicorn signal 启动。

复现入口：`docs/deployment/docker-loongarch-deployment.md`。
## 最新交接补充：MinerU 文档解析主链路（2026-06-09）

MinerU 已在 Windows 本地开发环境安装并接入资料上传主链路：

1. 依赖清单：`backend/requirements-mineru.txt`，当前锁定 `mineru[all]==3.2.3`。
2. 安装命令：`.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-mineru.txt`。
3. CLI 验证：`.\backend\.venv\Scripts\mineru.exe --version` 返回 `mineru, version 3.2.3`。
4. 主链路：`POST /api/knowledge/documents -> parser_router -> mineru_adapter -> parsed artifacts -> pending_review chunks`。
5. 支持范围：PDF / DOCX / PPTX / XLSX 优先走 MinerU；图片仍走 OCR / 多模态分析链路。
6. 产物目录：`data/knowledge/parsed/{document_id}/raw_parse_result.json`、`parsed.md`、`assets/`。
7. 审核边界：MinerU 解析生成的 chunks 默认 `review_status=pending_review`，审核通过前不进入正式 RAG 检索或 Chroma 同步。
8. 降级边界：未安装、关闭、超时、返回错误或无可用输出时自动 fallback，不阻断上传接口。
9. 配置开关：`MINERU_ENABLED=false` 可关闭真实解析；默认 `MINERU_BACKEND=pipeline`、`MINERU_LANG=ch`、`MINERU_TIMEOUT_SECONDS=180`。
10. 风险：MinerU 依赖体积大，LoongArch / Kylin 真实依赖尚未完整验收；国产化部署仍需单独记录安装和样本解析结果。

最新验证：

```text
backend tests: 139 passed in 22.98s
frontend build: passed
```

2026-06-25 文档同步口径：后端全量回归已更新为 `139 passed in 22.98s`；资料解析产物进入 `pending_review` 是当前真实规则，统一资料审核、状态机、审计事件和 readiness 检查均已完成。

详细说明：`docs/deployment/mineru-document-parsing.md`。
# 当前交接摘要（最终交付收口）

本仓库当前目标是比赛交付优先，不再扩展大功能。核心状态：

- 主链路：上传/解析 -> pending_review -> 审核 approved -> SQLite 向量索引 -> 检索 -> Evidence Pack -> RAG 结构化回答。
- 目标环境：LoongArch/银河麒麟默认使用 `RAG_VECTOR_STORE=sqlite`，不硬依赖 Chroma。
- 增强入口：`RAG_VECTOR_SQLITE_ENGINE=sqlite_vec`、`RAG_VECTOR_ENHANCER=qdrant|chroma` 均为可选；不可用时回退本地 SQLite。
- 真实 LLM：通过 OpenAI-compatible `.env` 配置接入，不提交 Key。
- 交付文档：见 `docs/product/final-delivery-summary.md`、`docs/product/demo-runbook-final.md`、`docs/product/defense-qa-final.md`、`docs/architecture/final-architecture.md`。

---
