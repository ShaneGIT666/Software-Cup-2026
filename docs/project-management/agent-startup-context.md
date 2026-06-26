# Coding Agent 初始化入口

## 最新启动入口（2026-06-06）

本地开发优先使用仓库根目录 `dev.bat` 统一管理前后端：

```bat
dev start
dev status
dev verify
dev logs
dev stop
dev restart
```

详细说明见 `docs/deployment/unified-dev-entry.md`。`start-dev.bat` 和 `stop-dev.bat` 仍保留，但已作为兼容包装转发到 `scripts/dev.ps1`。

启动后默认访问 `http://127.0.0.1:5173/`，后端健康检查为 `http://127.0.0.1:8000/api/health`。

更新时间：2026-06-25
用途：所有后续 Coding Agent 在没有对话上下文时的第一阅读入口。
规则：如果本文与其他历史文档冲突，以本文和 `docs/project-management/current-handoff.md` 为准。
文档规范：后续所有文档必须在不依赖聊天记录或隐含上下文的情况下，让 agent 和开发者清晰了解当前开发进度、软件功能、验证状态、风险边界和下一步任务；若变更 API、数据状态、部署方式、演示路径、风险口径或任务优先级，必须同步更新本文和 `current-handoff.md`。

## 1. 项目一句话

本项目是中国软件杯 A1 赛题“基于多模态大模型技术的设备检修知识检索与作业系统”的比赛作品。当前目标是两天内完成比赛交付收口：资料入库、检索、RAG 引用、作业流程、知识沉淀、审核审计、真实模型复验、弱网兜底和 LoongArch/Kylin 部署链路。

## 2. 最新事实

1. LoongArch / 银河麒麟 V11 后端最小依赖和 Docker 一体化部署均已验证；比赛提供环境需要使用最新提交重新复验并留证。
2. 目标 VM 无 npm/git 时，前端采用 Windows 本地构建 `frontend/dist`，再由 FastAPI 静态托管。
3. Windows 本地主线后端全量测试最新结果为 `139 passed in 22.98s`。
4. 前端生产构建已通过；存在 VueUse pure annotation 和 Vite chunk size warning，不阻塞。
5. 准生产 readiness 检查和 JSON 存储巡检已通过。
6. Qwen / DashScope OpenAI-compatible 文本 RAG 历史小样本验收通过；比赛最终模型需用目标环境、最终 `base_url`、模型名和 Key 重新复验。
7. Chroma 是可选向量索引增强；hash embedding 是断网和无 Key 场景的 fallback/占位，不是生产级语义 embedding。
8. 真实多模态 API 有小样本验收接口，但默认演示仍可使用 mock 兜底。
9. OCR 已新增可选 provider 层：默认 `OCR_PROVIDER=mock`，可选 `rapidocr` 或 `tesseract`；OCR/多模态文本会并入资料分析 chunks，但默认 `review_status=pending_review`，审核通过后才进入检索、RAG citations、Chroma 和知识关系网络。真实 OCR 依赖需单独安装 `backend/requirements-ocr.txt` 并记录 LoongArch/Kylin 兼容性。

## 3. 核心闭环

```text
输入设备型号和故障现象
-> 检索手册、历史案例、已审核入库资料和可选 Chroma 召回
-> 查看命中原因、来源、排序分和 citations
-> 生成 RAG 辅助建议
-> 查看标准化作业流程
-> 上传维修手册、现场图片或经验资料
-> parser_router/MinerU/OCR/多模态分析资料并生成 pending_review 知识片段
-> 统一审核工作台通过后进入正式检索/RAG/Chroma
-> 提交维修案例
-> 审核通过后再次检索命中新案例
-> 审计流水记录 reviewer/action/reason/before/after
```

## 4. 关键文件

1. 后端入口：`backend/app/main.py`
2. 检索与案例服务：`backend/app/services.py`
3. RAG provider：`backend/app/llm_adapter.py`
4. 多模态 provider：`backend/app/multimodal_adapter.py`
5. OCR provider：`backend/app/ocr_adapter.py`
6. 资料入库：`backend/app/knowledge.py`
7. Chroma 可选索引：`backend/app/vector_store.py`
8. JSON 原子写与备份恢复：`backend/app/data_store.py`
9. 前端入口：`frontend/src/App.vue`
10. 前端 API 类型：`frontend/src/api.ts`
11. 当前交接：`docs/project-management/current-handoff.md`
12. 测试报告：`docs/testing/software-test-report.md`
13. LoongArch 验证：`docs/deployment/loongarch-kylin-verification.md`
14. 最终交付审计：`docs/project-management/global-closure-audit-2026-06-24.md`

## 5. 常用命令

后端测试：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests/ -q
```

前端构建：

```powershell
cd frontend
npm.cmd run build
```

本地开发启动：

```powershell
.\start-dev.bat
```

准生产 readiness：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
```

JSON 存储巡检：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
```

构建前端 dist：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-frontend.ps1
```

打包 LoongArch 演示包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1
```

API 配置：

```powershell
.\configure-api.bat
```

## 6. 关键配置

离线兜底：

```env
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
RAG_VECTOR_STORE=off
```

Qwen 文本 RAG：

```env
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_API_STYLE=chat_completions
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
OPENAI_API_KEY=your-key
```

FastAPI 托管前端：

```env
SERVE_FRONTEND=auto
FRONTEND_DIST_DIR=../frontend/dist
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
```

OCR 可选增强：

```env
OCR_PROVIDER=mock
OCR_LANG=ch
```

真实本地 OCR 可先评估 `rapidocr` 或 `tesseract`。相关依赖放在 `backend/requirements-ocr.txt`，不要并入默认后端依赖。

## 7. 风险口径

1. 不要把 mock 多模态分析说成生产级 OCR。
2. 不要把轻量知识关系网络说成完整图数据库或生产级知识图谱。
3. 不要把 hash embedding 说成真实语义 embedding。
4. 不要提交 `.env`、官方 PDF、`data/uploads/`、`data/knowledge/`、`frontend/dist/`、`node_modules/`、`.venv/`。
5. 真实多模态 API 只做小样本验收，不承诺所有 OpenAI-compatible 网关都支持图片/PDF。
6. 真实 OCR 是可选增强，不是默认生产级能力；RapidOCR、PaddleOCR、Docling、MinerU 等依赖在 LoongArch/Kylin 上必须单独验收。
7. LoongArch 后端最小依赖和 Docker 一体化链路已有验证记录；最终环境仍需保留 FastAPI 静态托管前端访问和增强依赖关闭/降级的复验证据。
8. JSON 存储已有 `.bak` 恢复和巡检脚本，但不是高并发生产数据库。

## 8. 接手流程

1. 执行 `git status --short --branch`，确认工作区。
2. 阅读 `current-handoff.md` 和官方赛题基线。
3. 运行后端测试、前端构建、readiness 和 JSON 存储巡检。
4. 若改 API、数据状态、演示路径、部署方式或风险边界，必须同步更新本文和交接文档。
5. 不使用 `git reset --hard` 或 `git checkout --` 回滚协作者改动。
# Docker 部署快速入口（2026-06-06 最新）

后续 agent 如果需要继续国产化部署验证，应从 `docs/deployment/docker-loongarch-deployment.md` 开始。当前新增的 Docker 脚本入口是：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-docker-vm.ps1
```

默认目标是 LoongArch / Kylin VM，容器内提供 FastAPI API 与 `frontend/dist` 静态前端。部署脚本不保存 sudo 密码；如果远程 `sudo -n docker info` 不可用，脚本会停止并提示在 VM 内手动执行 Docker 预处理命令。

重要边界：仓库默认不提交 `frontend/dist`。如果 VM 通过 GitHub 源码 zip 拉取时缺少 dist，应使用包含 dist 的 GitHub Release/Artifact zip，并通过 `-PackageUrl` 传给部署脚本。
# 最新事实：Docker 国产化验证已通过（2026-06-06）

后续 agent 接手时必须知道：LoongArch / Kylin V11 Docker 一体化部署已经真实跑通，不再是待验证项。

已验证：

1. Docker 镜像 `software-cup-demo:loongarch` 在 `loongarch64` VM 上构建成功。
2. Docker 容器 `software-cup-demo` 启动成功。
3. `GET /api/health`、`GET /api/providers/status`、`GET /` 均通过。
4. Docker 默认使用离线兜底：`REMOTE_API_MODE=off`、`LLM_PROVIDER=mock`、`MULTIMODAL_PROVIDER=mock`、`RAG_VECTOR_STORE=off`。

复现与风险边界见 `docs/deployment/docker-loongarch-deployment.md`。
# Agent 启动上下文（最终交付版）

如果新 agent 接手，请先执行：

```powershell
git status --short --branch
git log --oneline -5
```

当前代码冻结方向：

- 不再迁移数据库、不引入大型 RAG 框架、不重做 UI 架构。
- 保持 FastAPI + Vue 3 + SQLite vector store 主链路。
- 所有上传解析、OCR、多模态和人工修正产物默认 pending_review。
- 正式检索/RAG 只使用 approved evidence。
- LoongArch/银河麒麟交付优先：Chroma 不是主依赖，sqlite-vec/Qdrant 是可选增强。

必要验证：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\ -q
cd frontend; npm.cmd run build
powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
git diff --check
```

---
