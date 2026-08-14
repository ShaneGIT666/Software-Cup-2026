# 目标环境强约束审计（2026-06-26）

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 结论

比赛交付主链路必须以 LoongArch + 银河麒麟/Kylin 的真实可运行结果为准。所有无法在目标环境闭环运行的依赖，不进入主交付链路；只能作为可选适配器、后续增强或研究路线保留。

当前修正后的主链路为：

```text
LoongArch/Kylin Docker
-> FastAPI + Vue dist 静态托管
-> JSON 业务数据持久化
-> pypdf PDF 文本解析 fallback
-> pending_review 审核隔离
-> approved-only 关键词检索 + SQLite 向量索引
-> OpenAI-compatible Qwen 真实 LLM
-> RAG answer + citations + fallback
```

## 官方约束复核

赛题 A1 的核心要求包括：

- 支持本地部署大模型服务或云端大模型服务，并提供 PC Web 或 App 可视化界面。
- 支持文本、故障图片、设备型号等多类型输入，实现知识检索与跨模态匹配。
- 提供标准化作业指引、合规提醒、个性化流程推荐。
- 支持一线人员上传案例、经验总结、审核入库、人工修正与知识更新。
- 交付环境必须面向 LoongArch CPU 与银河麒麟服务器操作系统。

其中 LoongArch/Kylin 是硬约束，不是性能优化项。技术路线必须先满足目标环境，再谈成熟度和功能增强。

## 目标环境证据

| 能力 | 状态 | 证据与处理 |
| --- | --- | --- |
| Docker 运行 | 保留 | 已在 LoongArch/Kylin VM 使用 Loongnix Python 3.11 镜像跑通。 |
| FastAPI 后端 | 保留 | `/api/health`、状态页、检索、RAG、上传审核链路已跑通。 |
| Vue 前端 | 保留 | 本地构建 `frontend/dist` 后由 FastAPI 静态托管，适合无 npm 的目标环境。 |
| 真实 LLM | 保留 | OpenAI-compatible Qwen 服务已在 VM 验证非 mock RAG 返回。 |
| JSON 业务存储 | 保留 | 纯文件读写，无原生依赖，适合目标环境。 |
| PDF 文本解析 | 保留 | `pypdf` 加入默认依赖后，目标容器 PDF 上传可生成 `pending_review` chunk。 |
| SQLite 向量索引 | 主链路 | 使用 Python 标准库 `sqlite3`，默认 `RAG_VECTOR_STORE=sqlite`，只索引 approved chunk。 |
| JSON 向量索引 | 兜底 | 纯 Python 文件索引，可在 SQLite 不可用时保留最小向量召回。 |
| Chroma | 替换 | `chromadb` / `chroma-hnswlib` 在 loongarch64 安装失败，不能作为主依赖。 |
| MinerU | 可选 | 当前 VM 未安装、不可用，不能作为交付主依赖；保留 adapter 和 fallback。 |
| Tesseract OCR | 可选 | Host 存在，但容器 apt 安装不稳定；不能作为默认 Docker 依赖。 |
| RapidOCR/PaddleOCR | 待验证 | 依赖 ONNX/深度学习运行时，必须目标环境安装验证后才能纳入主链路。 |
| 本地 LLM | 待验证 | 只有目标环境真实运行的本地服务才可纳入；当前主链路采用云端 Qwen。 |
| 外部图数据库 | 舍弃 | 两天交付不引入 Neo4j/PostgreSQL/复杂图数据库。 |

## 依赖审计

### 默认保留

- `fastapi`
- `uvicorn`
- `python-multipart`
- `httpx`
- `pypdf`
- Python stdlib `sqlite3`
- Vue 3、Vite、Element Plus、lucide icons

这些依赖要么已经在目标容器中跑通，要么是前端构建期依赖，不要求目标环境安装 Node。

### 默认移出主链路

- `chromadb`：移到 `backend/requirements-rag.txt`，只在非 LoongArch 或已验证环境显式安装。
- `mineru[all]`：保留 `backend/requirements-mineru.txt`，但不进入 Docker 默认安装。
- `rapidocr-onnxruntime`：保留 `backend/requirements-ocr.txt`，但不进入 Docker 默认安装。
- `tesseract-ocr`：Dockerfile 提供 `INSTALL_TESSERACT=true` 可选开关，默认关闭。

## 从成熟开源方案提取的技术路线

| 成熟项目/方案 | 提取内容 | 本项目采用方式 |
| --- | --- | --- |
| RAGFlow | 文档解析产物、审核前隔离、证据追溯 | 使用 `pending_review -> approved`，保留 parser artifacts 和 citation 字段。 |
| Haystack | 检索 pipeline 组件边界 | 后续按 query normalization、metadata filter、retriever、fusion、evidence builder 拆分，但不引入运行时。 |
| LlamaIndex | metadata-rich chunk、node/citation 结构 | chunk 保留设备型号、部件、故障码、page、section、version、review_status。 |
| PostgreSQL + pgvector | 成熟生产级向量数据库路线 | 作为 P1 候选；通过 LoongArch/Kylin 编译和服务验证后再接入。 |
| SQLite / sqlite-vec | 嵌入式向量存储路线 | 当前先用 stdlib SQLite 线性向量索引；`sqlite-vec` 待目标编译验证。 |
| Qdrant | payload filter + vector retrieval 思路 | 借鉴过滤和索引设计；官方架构不覆盖 LoongArch，暂不作为主依赖。 |
| Dify/FastGPT/Open WebUI | Provider 配置、模型状态、知识库操作 | 保留 `/api/providers/status`、OpenAI-compatible 配置、fallback 可见性。 |
| Ragas/DeepEval | 检索指标和用例驱动评测 | 采用轻量 eval runner，不引入重型评测框架运行时。 |
| MinerU/Docling/PaddleOCR/RapidOCR | 文档布局/OCR 能力边界 | 借鉴 adapter 和 artifacts 设计；依赖必须目标验证后才能启用为主链路。 |

## 当前必须修正的宣传口径

不能说：

- “Chroma 是主向量库。”
- “MinerU 已在比赛环境跑通。”
- “OCR/多模态解析完全生产可用。”
- “本地大模型已经部署。”

可以说：

- “目标环境主链路采用 SQLite 向量索引，Chroma 作为可选增强。”
- “SQLite 向量索引只同步 approved 片段，pending_review 不进入正式召回。”
- “MinerU adapter 已预留，当前目标环境会优雅降级到 pypdf/mock parser。”
- “图片/OCR/视觉分析具备接口和 fallback，真实 OCR 引擎需按目标环境验证结果启用。”
- “真实 Qwen LLM 已通过 OpenAI-compatible 云端服务在目标环境验证。”

## 后续准入规则

任何新能力进入主链路前，必须同时满足：

1. 能在 LoongArch/Kylin Docker 或目标 VM 原生环境安装。
2. 有可复现命令和日志。
3. 不依赖未提交的本机环境或 Windows-only 工具。
4. 失败时不阻塞上传、审核、检索、RAG 主链路。
5. 状态页能显示 provider、fallback 和错误原因。

不满足以上条件的能力，只能进入 optional adapter、研究文档或演示外备选，不允许写入最终主交付声明。
