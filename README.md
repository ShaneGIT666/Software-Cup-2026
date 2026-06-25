# 设备检修知识检索与作业辅助系统

本项目为第十五届中国软件杯 A 组赛题 A1“基于多模态大模型技术的设备检修知识检索与作业系统”的参赛作品仓库。

系统面向工业、能源、制造等场景中的设备检修作业，目标是通过多模态大模型、知识检索、标准化作业流程和经验案例沉淀，帮助一线检修人员更快查找资料、诊断故障、规范作业，并让维修经验持续进入知识库。

## 当前验证状态

| 项目 | 当前状态 |
| --- | --- |
| 后端自动化测试 | `139 passed in 22.98s`，覆盖检索、资料入库、审核状态机、RAG、OCR/MinerU fallback、评测 runner、审计事件和存储恢复 |
| 前端生产构建 | `npm.cmd run build` 通过；VueUse pure annotation 与 Vite chunk size warning 不阻塞演示 |
| 本地交付检查 | `run-production-readiness-check.ps1` 通过；`run-json-store-maintenance.ps1` 检查 4 个 JSON 文件健康 |
| LoongArch / 银河麒麟 | Docker 一体化链路已验证；比赛提供环境到手后需用最新提交重新复验并留证 |
| 前端目标环境托管 | 已支持 FastAPI 静态托管 `frontend/dist`，适配无 npm/nginx 的演示环境 |
| 真实文本大模型 | 支持 OpenAI-compatible provider；比赛演示需重新配置真实 `base_url`、模型和 Key 复验 |
| Chroma 向量增强 | 可选开启；`hash` embedding 明确为 fallback，占位不冒充生产级语义向量 |
| 多模态能力 | OCR/多模态链路具备 mock 兜底；真实 provider 需在目标环境通过 validate 接口小样本验收 |
| 现场兜底 | `REMOTE_API_MODE=off` 可强制本地 mock/检索链路，避免弱网断链 |

## 参赛信息

| 项目 | 内容 |
| --- | --- |
| 参赛编号 | 65013181 |
| 队名 | �錕斤拷錕斤拷��� |
| 题号 | A1 |
| 队长 | 刘子翔 |
| 队伍成员 | 张倬然、周梓聪 |
| 指导老师 | 焦新涛 |
| 学校 | 华南师范大学 |

## 项目目标

第一阶段优先完成一个可演示、可部署、文档完整的 B/S 系统原型，覆盖以下核心能力：

1. 多模态知识检索：支持文本、设备型号、故障描述、图片等输入。
2. 标准化作业指引：按设备、故障和检修等级输出步骤化作业流程。
3. 知识沉淀更新：支持维修案例提交、审核、标注和入库。
4. 大模型辅助诊断：通过可替换模型适配层提供诊断建议和作业提醒。
5. 国产化部署说明：面向 LoongArch 架构和银河麒麟高级服务器操作系统保留适配记录。

## 推荐技术路线

根据前期调研，本项目推荐采用轻量、可替换、便于三人协作的架构：

| 模块 | 推荐方案 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus |
| 后端 | Python FastAPI |
| 开发数据库 | 本地 JSON 文件持久化，后续可迁移 SQLite |
| 检索方案 | 关键词/字段权重 + 可选 Chroma 向量混合检索，默认只检索 approved 知识 |
| 向量库 | Chroma MVP，Qdrant 二阶段 |
| 模型接入 | OpenAI-compatible Adapter，默认 Mock 模式 |
| 文档解析 | `parser_router -> mineru_adapter` 优先处理 PDF/DOCX/PPTX/XLSX；PDF 可 fallback 到 pypdf，Office 文档未装 MinerU 时 fallback 到 mock parser |
| 审核与审计 | 统一审核工作台 + 知识片段状态机 + revision + review audit events |
| 部署 | 本地脚本 + FastAPI 静态托管 + Docker/LoongArch 兜底部署 |

完整调研结论见：`docs/research/open-source-architecture-research.md`

## 仓库结构

```text
.
├── backend/                  # 后端 API、检索、模型适配、数据访问
├── frontend/                 # Web 前端页面、组件、接口调用
├── data/
│   ├── examples/             # 演示样例和种子数据
│   ├── knowledge/            # 运行期资料入库和知识片段（不提交 Git）
│   ├── manuals/              # 检修手册和知识资料
│   └── uploads/              # 开发期上传文件
├── deploy/                   # 部署配置和发布材料
├── docs/
│   ├── deployment/           # 本地运行、安装部署、国产化适配
│   ├── design/               # API、数据模型、系统设计
│   ├── product/              # 产品说明、演示脚本、PPT 材料
│   ├── project-management/   # 开发流程、任务分工、看板
│   ├── requirements/         # 需求分析、MVP 范围、样例数据计划
│   ├── research/             # 开源项目与技术架构调研
│   └── testing/              # 测试计划和测试报告
├── scripts/                  # 初始化、构建、测试等辅助脚本
└── tests/                    # 自动化测试和接口测试
```

## 开发前必读

建议团队成员按以下顺序阅读和确认：

0. `docs/requirements/official-problem-baseline.md`：官方赛题基线，固定题面、硬约束、当前对齐与差距。
1. `docs/project-management/agent-startup-context.md`：Coding Agent 第一入口，记录最新状态、风险、验证和下一步。
2. `docs/pre-development-index.md`：开发前期准备总览。
3. `docs/project-management/development-plan.md`：后续开发阶段、任务分流与验收计划。
4. `docs/project-management/model-task-classification.md`：高智能模型任务与普通模型任务分流。
5. `docs/project-management/ordinary-agent-development-guide.md`：普通模型 Agent 交接、执行边界与风险管理。
6. `docs/design/api-contract-draft.md`：前后端接口契约草案。
7. `docs/research/open-source-architecture-research.md`：开源项目与架构调研结论。

## MVP 演示主线

第一版系统优先跑通以下闭环：

```text
输入设备型号和故障描述
-> 返回知识检索结果、相关手册和历史案例
-> 查看标准化作业步骤、安全提醒和验收标准
-> 提交维修经验案例
-> 审核后进入知识库
-> 再次检索时可复用新案例
```

比赛交付前，优先保证“能打开、能搜索、能看步骤、能提交案例、能审核资料、能展示真实模型或稳定兜底、能在目标环境复验”。完整权限系统、数据库迁移和生产级视觉诊断不纳入两天交付范围。

同时必须持续对照 `docs/requirements/official-problem-baseline.md`：

1. LoongArch + 银河麒麟部署要求是最终硬约束，不是可选加分项。
2. 当前系统仍以文本检索和资料入库 MVP 为主，不能夸大为“已完成多模态跨模态检索”。
3. 当前知识沉淀能力应表述为“可审核更新的知识库雏形”，不能直接宣称“知识图谱已完成”。

## 统一启动入口（推荐）

本地开发优先使用根目录 `dev.bat` 统一管理前后端。它会在后台启动 FastAPI 与 Vite，记录 PID 和日志，并提供状态检查、健康检查、日志查看和停止能力。

```bat
dev start
dev status
dev verify
dev logs
dev stop
dev restart
```

启动后访问：

```text
http://127.0.0.1:5173/
```

常用命令说明：

1. `dev start`：启动后端 `127.0.0.1:8000` 和前端 `127.0.0.1:5173`。
2. `dev status`：查看进程、端口和访问地址。
3. `dev verify`：检查 `/api/health` 与前端首页是否可访问。
4. `dev logs`：查看最近的后端和前端日志。
5. `dev stop`：停止保存的进程，并清理 8000/5173 端口残留服务。

PowerShell 直连方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action start -OpenBrowser
```

`start-dev.bat` 和 `stop-dev.bat` 已保留为兼容入口，内部会转发到统一管理脚本。

## 本地运行

一键启动前后端开发服务：

```bat
start-dev.bat
```

或使用 PowerShell 脚本版本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

如果使用 `start-dev.bat`，会自动打开前后端两个独立 PowerShell 窗口。
如果使用 `scripts/start-dev.ps1`，当前 PowerShell 窗口会被占用，请保持窗口打开，停止时按 `Ctrl+C`。

启动后访问：

```text
http://localhost:5173
```

停止后台服务：

```bat
stop-dev.bat
```

或使用 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1
```

如果需要分别启动，也可以使用 `scripts/start-backend.ps1` 和 `scripts/start-frontend.ps1`。

## 当前状态

当前仓库已完成：

1. Vue 3 + TypeScript + Vite + Element Plus 工业检修指挥台界面。
2. FastAPI 后端 API，覆盖检索、诊断、RAG、资料入库、多模态分析、知识关系网络、案例提交、统一审核和审计流水。
3. 本地 JSON 样例数据、原子写入、`.bak` 恢复和巡检脚本，保留轻量架构和比赛现场兜底能力。
4. 检索、流程查看、资料上传/入库、pending_review、审核、RAG citations、案例提交、审计追踪、审核后再检索的闭环。
5. 资料入库支持 `pdf/txt/md/docx/pptx/xlsx/jpg/jpeg/png/webp`；解析或多模态分析生成的片段默认 `pending_review`，审核通过前不进入正式检索、RAG citations 或 Chroma。
6. RAG provider 支持 `mock/openai/anthropic` 和 OpenAI-compatible 云端服务；真实比赛模型需用最终 Key 与 base_url 复验。
7. Chroma 可选向量索引已接入；未安装、关闭或查询失败时自动降级，`hash` embedding 是 fallback，占位不冒充真实语义 embedding。
8. FastAPI 可选静态托管 `frontend/dist`，用于无 npm/nginx 的目标环境演示。
9. 后端全量测试 `139 passed in 22.98s`；前端生产构建通过；readiness 和 JSON 存储巡检通过。
10. Coding Agent 动态交接入口：`docs/project-management/agent-startup-context.md`。

下一步建议：

1. 在比赛提供环境上复验最新提交，记录系统信息、部署命令、接口结果和截图。
2. 配置真实 OpenAI-compatible LLM，至少完成一次 `fallback=false` 的 RAG 回答验收。
3. 整理最终产品说明书、演示 runbook、PPT 大纲和视频脚本。
4. 扩充评测样例并保存最终评测报告，明确真实模型结果与 fallback 结果。
5. 打包最终交付物，确认不包含 `.env`、上传资料、运行数据、`node_modules`、`.venv` 和 Key。
## 最新补充：MinerU 文档解析主链路（2026-06-09）

项目已在 Windows 本地后端虚拟环境中安装并验证 MinerU 3.2.3。PDF / DOCX / PPTX / XLSX 上传时优先通过 `parser_router -> mineru_adapter` 解析，成功后保存 `raw_parse_result.json`、`parsed.md` 和 `assets/`，并生成 `review_status=pending_review` 的知识片段。审核通过前，这些片段不会进入正式 RAG 检索或 Chroma 同步。

部署和验收说明见：`docs/deployment/mineru-document-parsing.md`。

关键配置：

```env
MINERU_ENABLED=true
MINERU_BACKEND=pipeline
MINERU_LANG=ch
MINERU_TIMEOUT_SECONDS=180
MINERU_API_URL=
```

安装命令：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-mineru.txt
```

当前验证：

```text
mineru, version 3.2.3
backend tests: 139 passed in 22.98s
frontend build: passed
```
