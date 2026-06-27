# 设备检修知识检索与作业辅助系统

本仓库是中国软件杯 A 组 A1 赛题“基于多模态大模型技术的设备检修知识检索与作业系统”的参赛作品。系统面向设备检修现场，提供资料入库、审核、知识检索、图片识别线索、标准作业步骤、智能检修建议、回答修正和经验沉淀闭环。

当前版本定位为可演示、可部署、可答辩的准生产级原型。默认主链路优先保证 LoongArch / 银河麒麟环境可运行；真实 LLM、MinerU、向量增强和多模态 provider 均可配置，失败时保留离线兜底能力。

## 前端入口

前端已调整为三个任务区域：

1. 检修助手：默认首页，面向一线检修人员。
2. 管理中心：面向管理员、班组长和知识维护人员。
3. 系统状态：面向运维、部署复验和答辩展示。

检修助手按 5 步组织主流程：

```text
描述故障 -> 查看依据 -> 生成指引 -> 复核修正 -> 提交经验
```

管理中心集中放置资料入库、待审核内容、审核记录和知识关系图。系统状态集中展示模型服务、OCR、多模态、向量检索、离线兜底、MinerU/Chroma 状态和初始化配置指引。

## 快速启动

推荐使用统一开发入口：

```bat
dev start
dev status
dev verify
dev logs
dev stop
```

也可以手动启动：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
cd frontend
npm.cmd run dev
```

访问：

```text
http://127.0.0.1:5173/
```

生产演示时可由 FastAPI 静态托管 `frontend/dist`。

## 初始化配置脚本

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1
```

Linux / Kylin / LoongArch：

```bash
bash scripts/init-config.sh
```

脚本支持两种模式：

- 离线演示模式：写入 `REMOTE_API_MODE=off`、`LLM_PROVIDER=mock`、`MULTIMODAL_PROVIDER=mock`、`OCR_PROVIDER=mock` 和本地检索兜底配置。
- 真实 LLM 模式：写入 OpenAI-compatible `OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_API_KEY`、`OPENAI_API_STYLE=chat_completions` 等配置。

`.env` 已被 `.gitignore` 忽略。脚本在覆盖前会备份旧 `.env`，并且只脱敏显示 API Key。

验证模型服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-provider.ps1
```

或：

```bash
bash scripts/validate-provider.sh
```

## 核心能力

- 多类型输入：设备型号、故障描述、检修等级、现场图片和维修资料。
- 图片识别线索：OCR / 多模态结果进入当前诊断上下文，用于增强检索，不直接作为未审核正式依据。
- approved-only 检索：正式检索、RAG 引用和知识关系图默认只使用已审核内容。
- 标准作业步骤：按设备、故障和检修等级展示检查步骤、安全提醒和验收标准。
- 智能检修建议：输出初步判断、检查步骤、维修步骤、安全提醒、验收标准、引用来源和不确定信息。
- 知识沉淀：资料片段、维修案例、回答修正均进入审核流程，通过后沉淀到知识库或轻量知识关系图。
- 知识关系图：展示设备、故障、资料、案例、流程、术语和回答修正之间的关系，提供摘要、图例、SVG 图谱和节点详情。
- 现场兜底：真实模型、OCR、向量或解析服务不可用时，系统仍可通过离线演示模式完成主流程。

## 技术路线

| 模块 | 当前方案 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus |
| 后端 | FastAPI |
| 存储 | JSON 原子写入与备份，运行数据不提交 |
| 检索 | approved-only 关键词检索 + 可选向量增强 + Evidence Pack |
| 向量 | 默认 SQLite python_scan / hash fallback，Chroma/Qdrant/sqlite-vec 为可选增强 |
| LLM | OpenAI-compatible adapter，mock/offline 仅作兜底 |
| 文档解析 | parser_router + MinerU adapter，未安装时优雅降级 |
| 多模态 | OCR/视觉 provider 可选，失败时降级到 OCR/文本 LLM/本地兜底 |
| 部署 | Docker 优先，venv + FastAPI 静态托管兜底 |

## 当前验证状态

| 项目 | 结果 |
| --- | --- |
| 后端全量测试 | `174 passed in 729.77s` |
| 前端生产构建 | `npm.cmd run build` 通过，本轮构建耗时约 `4.61s` |
| readiness | `success=true` |
| JSON 巡检 | `success=true`，`issueCount=0` |
| API 冒烟 | health、search、RAG、multimodal、feedback、knowledge graph 已验证 |
| LoongArch / Kylin | 已有主链路复验记录，最终提交前建议再跑 `scripts/loongarch-final-verify.sh` |

## 交付文档

- `docs/submission/01-软件功能需求分析文档.md`
- `docs/submission/02-软件功能设计文档.md`
- `docs/submission/03-软件产品说明书.md`
- `docs/submission/04-软件功能测试报告.md`
- `docs/submission/05-软件安装包及部署文档.md`
- `docs/product/demo-runbook-final.md`
- `docs/product/final-delivery-summary.md`
- `docs/ppt-assets/final-demo-script-7min.md`
- `docs/ppt-assets/screenshot-checklist-final.md`
- `docs/project-management/final-engineering-test-report.md`

## 安全边界

不要提交 `.env`、API Key、上传资料、运行知识库、日志、压缩包、视频、截图、`.venv`、`node_modules` 或 `frontend/dist`。真实模型能力以目标环境的 provider 验证结果为准；mock、hash、fallback 和轻量知识关系图不能包装成生产级能力。
