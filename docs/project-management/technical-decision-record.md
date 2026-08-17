# 技术选型记录

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

本文档记录开发前期关键技术决策。每个决策一旦确认，除非出现重大阻塞，不建议频繁变更。

## 1. 当前状态

| 决策项 | 当前结论 | 状态 | 负责人 | 备注 |
| --- | --- | --- | --- | --- |
| 前端框架 | Vue 3 + TypeScript + Vite | 建议采用 | A | 后台型系统开发效率高 |
| UI 组件库 | Element Plus | 建议采用 | A | 表单、表格、上传、步骤条成熟 |
| 后端框架 | Python FastAPI | 建议采用 | B | 适合 API、模型、OCR、检索生态 |
| 数据库 | SQLite | 建议采用 | B | 开发期简单，后续可迁移 PostgreSQL |
| 大模型方案 | OpenAI-compatible Adapter + Mock 默认模式 | 建议采用 | B | 可切换 Qwen、DeepSeek、Ollama、LiteLLM |
| 检索方案 | 关键词检索 + 来源引用，第二阶段接 Chroma | 建议采用 | B | 先保证闭环，再增强语义检索 |
| 向量库 | Chroma MVP，Qdrant 二阶段 | 建议采用 | B | 轻量起步，保留升级空间 |
| 文档解析 | Markdown/JSON/PDF 文本 MVP，PaddleOCR/MinerU/Docling 二阶段 | 建议采用 | B/C | 控制早期复杂度 |
| 文件存储 | 本地 `data/` 目录 | 建议采用 | B/C | 开发期足够 |
| 部署方式 | 本地脚本 MVP，Docker Compose 二阶段 | 建议采用 | C | 兼顾简单开发和后续交付 |
| 演示设备场景 | 摩托车发动机检修 | 建议采用 | 全员 | 贴合赛题参考手册 |

## 2. 推荐基线方案

用于团队没有强偏好时快速开工。

| 模块 | 推荐技术 | 理由 |
| --- | --- | --- |
| 前端 | Vue 3 + TypeScript + Vite | 初始化快，结构清晰，适合比赛后台系统 |
| UI | Element Plus | 提供成熟表单、表格、上传、步骤条组件 |
| 后端 | Python FastAPI | 接口开发快，模型服务接入方便 |
| 数据库 | SQLite | 无需额外服务，便于演示和提交 |
| ORM | SQLAlchemy 或 SQLModel | 便于后续迁移数据库 |
| 检索 | 关键词检索 + 来源引用，第二阶段接 Chroma | 先保证闭环，后续升级语义检索 |
| 向量库 | Chroma MVP，Qdrant 二阶段 | 轻量起步，保留过滤检索升级空间 |
| 模型 | OpenAI-compatible 接口适配层 | 可切换 Qwen、DeepSeek、Ollama、LiteLLM 等 |
| 文档解析 | Markdown/JSON/PDF 文本，后续接 PaddleOCR/MinerU/Docling | 避免第一阶段被复杂 OCR 阻塞 |
| 文档 | Markdown | 易维护，适合比赛提交前转 PDF |

## 3. 决策模板

后续做重要技术选择时，按以下格式追加。

```text
## 决策编号：TDR-001

主题：

日期：

参与人：

背景：

备选方案：

决定：

理由：

影响：

回滚条件：
```

## 4. 待确认问题

1. 团队成员更熟悉 Vue 还是 React。
2. 后端成员更熟悉 Python 还是 Node.js。
3. 是否已有可用的大模型 API Key。
4. 是否需要在无网络环境下演示。
5. 是否能拿到赛题提供的检修手册 PDF。
6. 最终部署环境是否必须真实 LoongArch 运行，还是只提交适配说明。

## 5. 调研依据

完整调研结论见：

```text
docs/research/open-source-architecture-research.md
```

其中对 Dify、RAGFlow、FastGPT、Open WebUI、LangChain、LlamaIndex、Haystack、Chroma、Qdrant、Milvus、PaddleOCR、MinerU、Docling、Atlas CMMS、openMAINT 等项目做了对比。
