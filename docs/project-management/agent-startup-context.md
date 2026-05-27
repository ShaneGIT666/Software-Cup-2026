# Coding Agent 初始化入口

更新时间：2026-05-27
用途：所有后续 Coding Agent 在没有对话上下文时的第一阅读入口。
规则：如果本文与其他历史文档冲突，以本文和 `docs/project-management/current-handoff.md` 为准。
文档规范：后续所有文档必须在不依赖聊天记录或隐含上下文的情况下，让 agent 和开发者清晰了解当前开发进度、软件功能、验证状态、风险边界和下一步任务；若变更 API、数据状态、部署方式、演示路径、风险口径或任务优先级，必须同步更新本文和 `current-handoff.md`。

## 1. 项目一句话

本项目是中国软件杯 A1 赛题“基于多模态大模型技术的设备检修知识检索与作业系统”的比赛作品。当前目标是形成稳定可演示的 MVP：资料入库、检索、RAG 引用、作业流程、知识沉淀、弱网兜底和 LoongArch/Kylin 部署链路。

## 2. 最新事实

1. LoongArch / 银河麒麟 V11 后端最小依赖验证已完成；后端测试子集 `39 passed`，`/api/health` 和 `/api/providers/status` 正常。
2. 目标 VM 无 npm/git，因此前端采用 Windows 本地构建 `frontend/dist`，再由 FastAPI 静态托管的方案。
3. Windows 本地主线后端测试最新结果为 `78 passed in 18.67s`。
4. 前端生产构建已通过；存在 Vite chunk size warning，不阻塞。
5. Qwen / DashScope OpenAI-compatible 文本 RAG 已完成真实 API 小样本验收，返回 `fallback=false` 且保留 citations。
6. Chroma 是可选向量索引增强；hash embedding 是断网和无 Key 场景的 fallback/占位，不是生产级语义 embedding。
7. 真实多模态 API 新增小样本验收接口，但默认演示仍可使用 mock 兜底。

## 3. 核心闭环

```text
输入设备型号和故障现象
-> 检索手册、历史案例、入库资料和可选 Chroma 召回
-> 查看命中原因、来源、排序分和 citations
-> 生成 RAG 辅助建议
-> 查看标准化作业流程
-> 上传维修手册、现场图片或经验资料
-> 多模态 mock/真实 provider 分析资料并生成知识片段
-> 提交维修案例
-> 审核通过后再次检索命中新案例
```

## 4. 关键文件

1. 后端入口：`backend/app/main.py`
2. 检索与案例服务：`backend/app/services.py`
3. RAG provider：`backend/app/llm_adapter.py`
4. 多模态 provider：`backend/app/multimodal_adapter.py`
5. 资料入库：`backend/app/knowledge.py`
6. Chroma 可选索引：`backend/app/vector_store.py`
7. JSON 原子写：`backend/app/data_store.py`
8. 前端入口：`frontend/src/App.vue`
9. 前端 API 类型：`frontend/src/api.ts`
10. 当前交接：`docs/project-management/current-handoff.md`
11. 测试报告：`docs/testing/software-test-report.md`
12. LoongArch 验证：`docs/deployment/loongarch-kylin-verification.md`

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
OPENAI_EMBEDDING_MODEL=text-embedding-v3
```

## 7. 风险口径

1. 不要把 mock 多模态分析说成生产级 OCR。
2. 不要把轻量知识关系网络说成完整图数据库或生产级知识图谱。
3. 不要把 hash embedding 说成真实语义 embedding。
4. 不要提交 `.env`、官方 PDF、`data/uploads/`、`data/knowledge/`、`frontend/dist/`、`node_modules/`、`.venv/`。
5. 真实多模态 API 只做小样本验收，不承诺所有 OpenAI-compatible 网关都支持图片/PDF。
6. LoongArch 后端已验证；前端完整访问需按 FastAPI 静态托管方案在 VM 上复验。

## 8. 接手流程

1. 执行 `git status --short --branch`，确认工作区。
2. 阅读 `current-handoff.md` 和官方赛题基线。
3. 运行后端测试和前端构建。
4. 若改 API、数据状态、演示路径、部署方式或风险边界，必须同步更新本文和交接文档。
5. 不使用 `git reset --hard` 或 `git checkout --` 回滚协作者改动。
