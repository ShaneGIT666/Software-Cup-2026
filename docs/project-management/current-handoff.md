# 当前开发交接说明

更新时间：2026-05-27
适用对象：后续 Coding Agent、协作者、人工复审人员。
优先级：任何后续开发前先读本文，再读 `docs/requirements/official-problem-baseline.md`。
文档规范：本文和后续所有项目文档必须上下文自包含，确保只 clone 仓库的 agent 或开发者也能理解开发进度、软件功能、验证状态、风险边界和下一步任务；不得依赖聊天记录补全含义。

## 1. 当前状态

项目目标仍是完成中国软件杯 A1 赛题“基于多模态大模型技术的设备检修知识检索与作业系统”。当前主线不是生产级重构，而是比赛作品收口：可部署、可演示、可解释、可兜底、可抗追问。

已确认事实：

1. Windows 本地主线后端测试最新结果为 `85 passed in 14.26s`，资料入库、RAG、上传安全、多模态/OCR mock、Chroma 可选召回和官方 PDF 流程均有覆盖。
2. 前端 `npm.cmd run build` 已通过；存在 Vite chunk size warning，不阻塞比赛演示。
3. Qwen / DashScope OpenAI-compatible 文本 RAG 已完成一次真实 API 小样本验收，返回 `fallback=false`，citations 保留。
4. LoongArch / 银河麒麟 V11 虚拟机已完成后端最小依赖验证，后端测试子集 `39 passed`，`/api/health` 与 `/api/providers/status` 正常。
5. 目标 VM 无 npm/git，因此前端采用 Windows 本地构建 `frontend/dist`，再由 FastAPI 静态托管的方案补齐。
6. 官方样例 PDF `E:/Download/Downloads/摩托车发动机维修手册.pdf` 只作为本地测试/演示输入，不得提交进 Git。
7. OCR 已作为可选增强接入：`OCR_PROVIDER=mock` 默认兜底，`rapidocr`/`tesseract` 可选；OCR 识别文本会进入资料 chunks，并被检索、RAG citations 和知识关系网络复用。

## 2. 已实现能力

后端：

1. `POST /api/search`：关键词加权检索，返回 `matchedTerms`、`reason`、`scoreBreakdown`。
2. `POST /api/diagnosis`：复用检索/RAG 管道生成结构化诊断，返回可能原因、排查动作、安全提醒和 citations，不再是固定硬编码结果。
3. `POST /api/rag/answer`：基于检索结果生成 RAG 回答，支持 mock/openai/anthropic、citations、上下文裁剪、token 控制和 fallback。
4. `POST /api/providers/llm/validate`：真实文本 LLM 小样本验收，只读取服务端环境变量，不接收前端 Key。
5. `GET /api/providers/status`：返回 LLM、多模态、OCR、embedding 和离线兜底状态。
6. `POST /api/knowledge/documents`：资料入库，支持 `pdf/txt/md/jpg/jpeg/png/webp`。
7. `POST /api/knowledge/documents/{document_id}/analyze`：对 PDF/图片资料做多模态分析和可选 OCR，并生成可检索 chunks。
8. `POST /api/providers/multimodal/validate`：真实多模态小样本验收入口，失败不影响主链路。
9. `POST /api/knowledge/graph`：轻量知识关系网络原型。
10. Chroma 可选向量索引：`RAG_VECTOR_STORE=chroma` 时启用；默认关闭，初始化或查询失败会降级为空召回。
11. FastAPI 可选托管前端：`SERVE_FRONTEND=auto` 且 `frontend/dist/index.html` 存在时，`/` 返回 SPA 页面。
12. JSON 持久化已使用临时文件 + `os.replace()` 原子替换，降低异常中断导致文件损坏的风险。

前端：

1. 工业检修指挥台风格 Web GUI。
2. 检索、结果证据、作业流程、资料入库、多模态分析、RAG 建议、知识关系网络、案例提交/审核的演示闭环。
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
OPENAI_EMBEDDING_MODEL=text-embedding-v3
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
5. OCR provider 是可选增强；RapidOCR、PaddleOCR、Docling、MinerU 等真实依赖需要单独记录安装命令、样本效果、许可证和 LoongArch/Kylin 风险。
6. LoongArch 后端已验证；前端完整浏览器访问需按 FastAPI 静态托管方案在 VM 上复验。
7. 不提交 `.env`、官方 PDF、`data/uploads/`、`data/knowledge/`、`frontend/dist/`、`node_modules/`、`.venv/`。

## 5. 推荐下一步

1. 面向评委整理最终产品说明书、演示 runbook、PPT 大纲和 7 分钟视频脚本。
2. 网络可用时安装 `@playwright/test`，运行 `npm run test:e2e`，把演示路径纳入自动化冒烟。
3. 如要展示真实多模态，只用一张小图片做 `POST /api/providers/multimodal/validate`，不要一次上传整本 PDF 消耗 token。
4. 如要展示真实 OCR，优先用 `backend/requirements-ocr.txt` 安装 RapidOCR，在 1 张现场小图上验证“识别文本 -> chunk -> search -> RAG citation”。
5. 按 `docs/superpowers/specs/2026-05-27-ceiling-improvement-design.md` 继续推进低风险提分项，例如扩展演示种子数据和演示检查清单。
6. 如恢复 LoongArch 工作，再上传最新 release 包，验证 `/`、`/api/health`、`/api/providers/status`。

## 6. 接手规则

1. 开始前执行 `git status --short --branch`。
2. 不使用 `git reset --hard` 或 `git checkout --` 回滚协作者改动。
3. 任何 API、数据状态、演示路径、风险边界变化，都必须同步更新本文。
4. 新增重依赖前先说明 LoongArch 风险，并保留 mock/offline 兜底。
# Docker 部署入口（2026-06-06 最新）

Docker 方案已经作为 LoongArch / Kylin V11 国产化部署验证的辅助路径补充进项目。后续 agent 接手时必须优先阅读 `docs/deployment/docker-loongarch-deployment.md`，再运行相关脚本。

当前 Docker 路线的边界如下：

1. Docker 默认使用离线兜底配置：`REMOTE_API_MODE=off`、`LLM_PROVIDER=mock`、`MULTIMODAL_PROVIDER=mock`、`RAG_VECTOR_STORE=off`。
2. VM 没有 `git/npm`，因此远程部署脚本优先通过 `curl` 下载 GitHub zip，不依赖 `git clone`。
3. 如果 GitHub 源码包不包含 `frontend/dist`，脚本会显式失败并提示使用包含 dist 的 GitHub Release/Artifact zip；不应在 VM 上临时安装 npm 来绕过该问题。
4. 脚本不会保存 sudo 密码；如果 `sudo -n docker info` 不可用，需先在 VM 终端手动完成 Docker 预处理。
5. Docker 是比赛演示和部署验证辅助方案，不替代原生 LoongArch/Kylin 运行验证要求。
# 最新交接补充：Docker 验证已完成（2026-06-06）

LoongArch / Kylin V11 Docker 一体化部署已完成真实验证。后续 agent 不应再把 Docker 部署描述为“待验证”。

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
backend API: 70 passed
frontend build: passed
```

详细说明：`docs/deployment/mineru-document-parsing.md`。
