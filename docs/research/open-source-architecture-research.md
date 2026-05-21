# 开源项目与技术栈调研结论

检索日期：2026-05-19

目标：围绕赛题“基于多模态大模型技术的设备检修知识检索与作业系统”，调研成熟开源项目和官方技术资料，明确开发前期的架构、技术栈、可借鉴能力与风险边界，减少后续返工。

## 1. 结论先行

本项目不建议直接 fork 或二次开发 Dify、RAGFlow、FastGPT、Open WebUI 这类完整平台。它们能力强，但整体较重，且部分项目存在额外许可证或品牌限制。三人比赛项目更适合采用“自研轻量业务系统 + 借鉴成熟 RAG 设计 + 预留可替换组件”的路线。

推荐基线架构：

```text
Vue 3 + TypeScript + Vite 前端
        |
FastAPI 后端 API
        |
业务服务层：检索 / 作业流程 / 案例沉淀 / 文件上传 / 模型适配
        |
SQLite 开发库 + 本地文件目录 + Chroma 向量索引
        |
OpenAI-compatible LLM Adapter
        |
云端模型 API / LiteLLM / Ollama / 本地模型服务
```

第一阶段建议：

1. 前端：Vue 3 + TypeScript + Vite + Element Plus。
2. 后端：Python FastAPI。
3. 数据库：SQLite 开发期，后续可迁移 PostgreSQL。
4. RAG：先做关键词检索 + 来源引用，再接 Chroma 向量检索。
5. 模型：统一封装 OpenAI-compatible 接口，不把业务代码绑定到某个模型厂商。
6. 文档解析：先支持 PDF 文本和 Markdown/JSON 样例，后续接 PaddleOCR、MinerU 或 Docling。
7. 多模态：MVP 阶段先实现图片上传和 OCR/多模态识别占位，第二阶段再增强。

## 2. 可借鉴的成熟 LLM/RAG 平台

| 项目 | 定位 | 可借鉴点 | 不建议直接采用的原因 |
| --- | --- | --- | --- |
| Dify | LLM 应用开发平台 | 工作流、RAG、模型管理、可观测性 | 平台较重，许可证有额外条件 |
| RAGFlow | 面向复杂文档的 RAG 引擎 | 深度文档理解、可解释切分、引用溯源 | 服务组件多，比赛项目直接集成成本高 |
| FastGPT | 中文生态知识库与 Agent 平台 | 知识库导入、RAG、可视化 Flow、OpenAI-compatible 模型接入 | 协议限制较多，不适合直接复制代码 |
| Open WebUI | 自托管 AI WebUI | 离线部署、文档 RAG、引用、混合检索 | 更像通用聊天入口，不是检修业务系统 |

### 2.1 Dify

官方仓库说明 Dify 是开源 LLM 应用开发平台，组合了 AI workflow、RAG pipeline、Agent、模型管理和可观测性能力。它还支持多模型供应商和 OpenAI-compatible 模型。参考：[Dify GitHub](https://github.com/langgenius/dify)。

可借鉴：

1. 将“大模型调用、知识检索、工作流、日志观测”拆成独立模块。
2. 后台配置模型供应商，业务层只依赖统一模型接口。
3. RAG 管道覆盖文档导入、抽取、切分、检索、回答生成。

注意：

1. Dify 仓库许可证是 Dify Open Source License，基于 Apache 2.0 但有额外条件。
2. 对三人比赛项目来说，直接使用 Dify 会削弱“自主开发系统”的呈现，也会带来部署和定制成本。

### 2.2 RAGFlow

RAGFlow 官方仓库定位为开源 RAG 引擎，重点是复杂文档理解、模板化切分、可追溯引用和多类型数据源。参考：[RAGFlow GitHub](https://github.com/infiniflow/ragflow)。

可借鉴：

1. “Quality in, quality out”：检索质量首先取决于文档解析与切分质量。
2. 检索结果必须带来源、片段、置信度，便于现场检修人员判断。
3. 支持人工干预切分和引用，是工业检修场景里很重要的可信设计。

注意：

1. RAGFlow 许可证为 Apache-2.0，更友好。
2. 但完整 RAGFlow 适合做平台，不适合作为本项目的直接后端底座。
3. 推荐把它作为 RAG 设计参考，而不是直接嵌入。

### 2.3 FastGPT

FastGPT 官方介绍其为知识库与 AI Agent 构建平台，提供数据处理、模型调用、RAG 检索和可视化工作流。参考：[FastGPT GitHub](https://github.com/labring/FastGPT)、[FastGPT 官网](https://labring.github.io/fastgpt-home/)。

可借鉴：

1. 中文知识库产品形态成熟，适合参考页面结构和知识库操作流程。
2. 文档导入覆盖 Word、PDF、Excel、Markdown、网页链接。
3. 支持 OpenAI API 对齐的模型接入方式，利于切换不同模型供应商。

注意：

1. FastGPT Open Source License 允许作为后台服务直接商用，但不允许未经授权提供 SaaS，并要求保留版权信息。
2. 本项目可以学习其交互和知识库能力，不建议复制代码。

### 2.4 Open WebUI

Open WebUI 是可自托管、可离线运行的 AI Web 平台，支持 Ollama、OpenAI-compatible API，并内置 RAG。参考：[Open WebUI GitHub](https://github.com/open-webui/open-webui)、[Open WebUI RAG 文档](https://docs.openwebui.com/features/rag)。

可借鉴：

1. 离线/自托管能力适合赛题国产化部署要求。
2. RAG 结果支持 citation，有助于减少大模型幻觉。
3. 官方 RAG 文档强调混合检索、rerank、相关度阈值和上下文长度。

注意：

1. Open WebUI 更偏通用聊天系统。
2. 本项目需要“设备、故障、作业流程、案例审核”的业务主线，因此不宜直接使用 Open WebUI 替代业务系统。

## 3. RAG 开发框架选择

| 框架 | 定位 | 适合本项目的用法 |
| --- | --- | --- |
| LangChain | RAG、Agent、工具调用生态 | 可在第二阶段引入，先保持后端简单 |
| LlamaIndex | 面向私有数据的上下文增强和 RAG | 可用于文档索引、查询引擎、数据连接器 |
| Haystack | 模块化 AI 编排框架 | 适合生产级 RAG pipeline，但初期略重 |

### 3.1 LangChain

LangChain 官方文档将 RAG 描述为在查询时检索外部知识，并把相关内容提供给 LLM 生成答案。其检索模块由 loaders、splitters、embeddings、vector stores 等可替换组件组成。参考：[LangChain Retrieval 文档](https://docs.langchain.com/oss/python/langchain/retrieval)。

建议：

1. 第一阶段不要过早引入复杂 Agent。
2. 可以先按 LangChain 的模块思路设计接口：Loader -> Splitter -> Embedder -> Retriever -> Generator。
3. 业务代码中保留可替换接口，后续需要时再接 LangChain。

### 3.2 LlamaIndex

LlamaIndex 官方文档强调 context augmentation，即把私有数据、PDF、数据库、API 等转成 LLM 可用的上下文。参考：[LlamaIndex 文档](https://developers.llamaindex.ai/python/framework/)。

建议：

1. 适合后续做“检修手册 + 案例 + 数据库”的统一查询。
2. 如果后端使用 FastAPI，LlamaIndex 可以作为检索服务内部模块。
3. MVP 阶段先不用，避免技术栈膨胀。

### 3.3 Haystack

Haystack 官方定位为开源 AI 编排框架，支持 Agents、multimodal apps、scalable RAG systems，核心是 components、pipelines、Document Stores 等。参考：[Haystack 文档](https://docs.haystack.deepset.ai/docs/intro)。

建议：

1. 如果后期追求生产级 pipeline、可测试检索流程，可以参考 Haystack。
2. 三人比赛项目初期不建议引入，除非后端成员已经熟悉。

## 4. 向量数据库选择

| 方案 | 优点 | 风险 | 推荐阶段 |
| --- | --- | --- | --- |
| Chroma | 本地轻量、上手快、Apache 2.0 | 单机为主，复杂生产能力弱 | MVP |
| Qdrant | Rust 实现，过滤能力强，API 完整，Apache 2.0 | 需要单独服务 | 第二阶段 |
| Milvus | 大规模向量检索成熟，Apache 2.0 | 部署和资源要求更高 | 后期扩展 |

### 4.1 Chroma

Chroma 官方文档说明其是开源 AI 数据基础设施，Apache 2.0 许可。参考：[Chroma Open Source 文档](https://docs.trychroma.com/docs/overview/oss)。

建议：

1. 适合 MVP 阶段做本地向量索引。
2. 便于提交和演示，不需要复杂部署。
3. 要把原始 Markdown/JSON 作为知识源，向量库只作为可重建索引。

### 4.2 Qdrant

Qdrant 官方仓库说明它是向量相似度搜索引擎和向量数据库，提供 payload 过滤能力，使用 Apache 2.0 许可。参考：[Qdrant GitHub](https://github.com/qdrant/qdrant)。

建议：

1. 当需要按设备型号、故障类型、审核状态进行过滤检索时，Qdrant 更合适。
2. 如果第二阶段要增强检索质量，可从 Chroma 切到 Qdrant。

### 4.3 Milvus

Milvus 官方文档说明其适合从本地原型到大规模分布式向量检索，支持文本、图片、多模态等非结构化数据。参考：[Milvus 文档](https://milvus.io/docs/overview.md)。

建议：

1. 适合写在“后续扩展方案”里。
2. 不建议作为三人 MVP 首选，部署成本偏高。

## 5. 文档解析、OCR 与多模态

| 工具 | 定位 | 适合用途 | 建议 |
| --- | --- | --- | --- |
| PaddleOCR | 中文/多语言 OCR | 故障图片、扫描手册文字识别 | 第二阶段重点考虑 |
| MinerU | 文档解析为 Markdown/JSON | PDF、Office、图片转 RAG 友好格式 | 第二阶段考虑 |
| Docling | 文档转换与解析 | PDF/Office 转结构化内容 | 第二阶段考虑 |
| Unstructured | 文档 ETL | 多格式文档切分和元数据 | 可选 |

### 5.1 PaddleOCR

PaddleOCR 官方文档定位为多语言、实用 OCR 工具。它支持文档布局检测、公式识别、多语言模型等能力。参考：[PaddleOCR 文档](https://www.paddleocr.ai/main/en/index/index.html)。

建议：

1. 赛题强调多模态输入，PaddleOCR 很适合作为图片/扫描手册的 OCR 备选。
2. MVP 先实现图片上传和识别结果占位。
3. 第二阶段再接入 OCR，避免早期环境问题拖慢主线。

### 5.2 MinerU

MinerU 生态仓库说明其可将 PDF、Word、PPT、图片、网页解析为 Markdown/JSON，并支持 RAGFlow、Dify、FastGPT、LangChain 集成。参考：[MinerU Ecosystem GitHub](https://github.com/opendatalab/MinerU-Ecosystem)。

建议：

1. 如果赛题手册 PDF 结构复杂，MinerU 值得优先验证。
2. 解析结果应存成 Markdown/JSON，作为知识库源文件。

### 5.3 Docling

IBM 介绍 Docling 是开源文档解析工具，可将文档导出为适合后续处理的格式。参考：[IBM Docling 教程](https://www.ibm.com/think/tutorials/build-document-question-answering-system-with-docling-and-granite)、[Docling GitHub 组织](https://github.com/docling-project)。

建议：

1. 适合英文/复杂 PDF 的结构化解析。
2. 中文维修手册场景下需要先做小样本验证。

## 6. 设备检修业务系统参考

| 项目 | 定位 | 可借鉴业务能力 | 注意事项 |
| --- | --- | --- | --- |
| Atlas CMMS | 自托管维修管理系统 | 设备、工单、维护记录、库存、报表 | AGPL/商业双许可，不建议复制代码 |
| openMAINT / CMDBuild | 资产与设施维护管理系统 | 资产模型、维护活动、物流经济管理 | 偏企业级，架构复杂 |

### 6.1 Atlas CMMS

Atlas CMMS 官方仓库说明其是自托管 CMMS，覆盖工单、设备、库存、用户角色、流程和报表。技术栈包括 Spring Boot、React/TypeScript、React Native。参考：[Atlas CMMS GitHub](https://github.com/grashjs/cmms)。

可借鉴：

1. 设备资产、工单、维护记录、库存这些实体关系。
2. “像技术人员的 Jira”这种产品表达，适合答辩讲解。
3. 维修历史、停机时间、成本分析等可以作为后续商业价值。

注意：

1. Atlas 使用 AGPL-3.0/商业双许可，不能随意复制代码。
2. 本项目重点是知识检索与作业辅助，不需要完整 CMMS。

### 6.2 openMAINT / CMDBuild

CMDBuild 官方说明其是用于资产管理自定义应用的开源 Web 环境，openMAINT 是其面向物业和设施维护管理的垂直方案。参考：[CMDBuild 官网](https://www.cmdbuild.org/en)、[openMAINT 官网](https://www.openmaint.org/en/home)。

可借鉴：

1. 资产管理系统的领域结构：资产、位置、维护活动、经济管理、文档。
2. 本项目可将“设备档案 + 检修案例 + 作业流程”作为轻量版领域模型。

注意：

1. openMAINT 更偏传统 CMMS，不是大模型知识检索系统。
2. 只适合作为领域模型参考。

## 7. 模型接入与可替换策略

本项目必须避免绑定单一模型厂商。推荐统一使用 OpenAI-compatible 适配层：

```text
业务服务 -> LLM Adapter -> OpenAI-compatible Client -> Qwen / DeepSeek / Ollama / LiteLLM / 其他服务
```

参考资料：

1. Ollama 官方支持部分 OpenAI API 兼容能力，便于本地模型接入：[Ollama OpenAI compatibility](https://docs.ollama.com/openai)。
2. LiteLLM 官方支持用 OpenAI 格式调用 100+ LLM，并可作为统一代理：[LiteLLM 文档](https://docs.litellm.ai/)。

建议：

1. MVP 默认 `LLM_PROVIDER=mock`，无模型密钥也能演示。
2. 真实 API 只通过 `.env` 配置，不写死在代码里。
3. 提示词、模型名、温度、超时、重试策略放在后端配置层。
4. 返回结果必须包含 `fallback` 字段，标记是否为降级响应。

## 8. 推荐最终技术栈

### 8.1 前端

推荐：

```text
Vue 3 + TypeScript + Vite + Element Plus
```

依据：

1. Vue 官方文档说明 Vue 本身使用 TypeScript，并提供一等 TypeScript 支持。
2. 官方 `create-vue` 可创建 Vite 驱动、TypeScript 就绪项目。
3. Vue CLI 已进入维护模式，新项目推荐 Vite。

参考：[Vue TypeScript 文档](https://vuejs.org/guide/typescript/overview)。

原因：

1. 后台型系统页面多为表单、表格、上传、步骤流，Element Plus 组件更省时间。
2. 国内资料丰富，三人协作成本低。

### 8.2 后端

推荐：

```text
Python FastAPI + Pydantic + SQLAlchemy/SQLModel
```

依据：

FastAPI 官方定位为基于 Python 类型提示的现代高性能 API 框架，并带自动交互式 API 文档。参考：[FastAPI 官方文档](https://fastapi.tiangolo.com/)。

原因：

1. 与模型、OCR、文档解析、向量检索生态更贴近。
2. 自动 OpenAPI 文档有利于前后端联调。
3. 三人小队能快速做出 API 闭环。

### 8.3 数据与检索

推荐：

```text
SQLite + Markdown/JSON 源文件 + Chroma 向量索引
```

后续升级：

```text
PostgreSQL + Qdrant
```

原因：

1. SQLite 开发和提交最简单。
2. Markdown/JSON 作为知识源，向量索引可重建。
3. Qdrant 可在需要过滤检索和稳定服务时替换 Chroma。

### 8.4 部署

推荐：

```text
第一阶段：手动启动脚本 + 文档
第二阶段：Docker Compose
```

依据：

1. Docker Compose 官方定位是定义和运行多容器应用，适合统一管理服务、网络、卷和生命周期。参考：[Docker Compose 文档](https://docs.docker.com/compose)。
2. FastAPI 官方提供容器部署说明。参考：[FastAPI Docker 部署](https://fastapi.tiangolo.com/deployment/docker/)。
3. openEuler 文档显示其提供 iSulad 和 Docker 容器引擎包，并覆盖 LoongArch 等架构。参考：[openEuler 容器文档](https://docs.openeuler.org/en/docs/24.03_LTS/docs/Container/container.html)、[openEuler 文档中心](https://docs.openeuler.org/)。

注意：

1. 比赛要求 LoongArch + 银河麒麟高级服务器操作系统，需避免只能在 x86 上运行的原生依赖。
2. 所有引入的 OCR、向量库、模型服务都要记录 LoongArch 兼容性风险。
3. MVP 尽量使用纯 Python/纯前端/通用 Linux 依赖。

## 9. 架构定稿建议

### 9.1 模块边界

```text
frontend/
  工作台
  知识检索
  检索结果
  作业指导
  案例提交
  案例审核

backend/
  api/
    health
    search
    diagnosis
    workflows
    cases
    uploads
  services/
    retrieval
    ingestion
    llm
    workflow
    case_review
  repositories/
    relational_db
    vector_store
    file_store
```

### 9.2 数据流

```text
资料导入
PDF/Markdown/JSON -> 文档解析 -> 切分 -> 元数据标注 -> 向量化 -> Chroma/Qdrant

检索问答
用户输入 -> 查询改写/关键词抽取 -> 混合检索 -> rerank 可选 -> 组装上下文 -> LLM -> 带引用答案

知识沉淀
案例提交 -> 待审核 -> 人工修正标签/原因/步骤 -> 审核通过 -> 进入可检索知识库
```

### 9.3 必须保留的可替换接口

| 接口 | 初始实现 | 可替换目标 |
| --- | --- | --- |
| `LLMProvider` | Mock + OpenAI-compatible | Qwen、DeepSeek、Ollama、LiteLLM |
| `VectorStore` | Chroma | Qdrant、Milvus |
| `DocumentParser` | Markdown/JSON/PDF 文本 | PaddleOCR、MinerU、Docling |
| `FileStorage` | 本地目录 | MinIO、对象存储 |
| `SearchStrategy` | 关键词 + 向量 | 混合检索、GraphRAG |

## 10. 不建议现在做的事

1. 不建议直接集成 Dify/RAGFlow/FastGPT 作为主系统。
2. 不建议第一版就做完整知识图谱。
3. 不建议第一版依赖 GPU、本地大模型或复杂 OCR。
4. 不建议第一版做完整权限系统。
5. 不建议先追求“全自动智能诊断”，应先保证“资料可查、步骤可信、来源可追溯”。

## 11. 对现有文档的修订建议

建议把 `technical-decision-record.md` 中的推荐方案更新为：

| 决策项 | 建议结论 |
| --- | --- |
| 前端框架 | Vue 3 + TypeScript + Vite |
| UI 组件 | Element Plus |
| 后端框架 | FastAPI |
| 开发数据库 | SQLite |
| 数据模型 | 设备、手册片段、故障案例、作业流程、上传文件 |
| RAG 初始方案 | 关键词检索 + 来源引用，随后接 Chroma |
| 向量库 | Chroma MVP，Qdrant 二阶段 |
| 文档解析 | Markdown/JSON/PDF 文本 MVP，PaddleOCR/MinerU/Docling 二阶段 |
| 模型接入 | OpenAI-compatible 适配层，默认 mock |
| 部署 | 本地脚本 MVP，Docker Compose 二阶段 |

## 12. 参考来源

1. [Dify GitHub](https://github.com/langgenius/dify)
2. [RAGFlow GitHub](https://github.com/infiniflow/ragflow)
3. [FastGPT GitHub](https://github.com/labring/FastGPT)
4. [FastGPT 官网](https://labring.github.io/fastgpt-home/)
5. [Open WebUI GitHub](https://github.com/open-webui/open-webui)
6. [Open WebUI RAG 文档](https://docs.openwebui.com/features/rag)
7. [LangChain Retrieval 文档](https://docs.langchain.com/oss/python/langchain/retrieval)
8. [LlamaIndex 文档](https://developers.llamaindex.ai/python/framework/)
9. [Haystack 文档](https://docs.haystack.deepset.ai/docs/intro)
10. [Chroma Open Source 文档](https://docs.trychroma.com/docs/overview/oss)
11. [Qdrant GitHub](https://github.com/qdrant/qdrant)
12. [Milvus 文档](https://milvus.io/docs/overview.md)
13. [PaddleOCR 文档](https://www.paddleocr.ai/main/en/index/index.html)
14. [MinerU Ecosystem GitHub](https://github.com/opendatalab/MinerU-Ecosystem)
15. [Docling GitHub 组织](https://github.com/docling-project)
16. [Atlas CMMS GitHub](https://github.com/grashjs/cmms)
17. [CMDBuild 官网](https://www.cmdbuild.org/en)
18. [openMAINT 官网](https://www.openmaint.org/en/home)
19. [Ollama OpenAI compatibility](https://docs.ollama.com/openai)
20. [LiteLLM 文档](https://docs.litellm.ai/)
21. [Vue TypeScript 文档](https://vuejs.org/guide/typescript/overview)
22. [FastAPI 官方文档](https://fastapi.tiangolo.com/)
23. [Docker Compose 文档](https://docs.docker.com/compose)
24. [FastAPI Docker 部署](https://fastapi.tiangolo.com/deployment/docker/)
25. [openEuler 容器文档](https://docs.openeuler.org/en/docs/24.03_LTS/docs/Container/container.html)
26. [openEuler 文档中心](https://docs.openeuler.org/)

## 13. 本次资料入库 MVP 的开源参考落地策略

更新日期：2026-05-21。

本次实现只落地“轻量资料入库 MVP”，不直接引入 Docling、MinerU、PaddleOCR、LlamaIndex 或 LangChain 作为运行时依赖。原因是当前项目首先要保证 Windows 本地环境、现有检索闭环和比赛演示稳定，避免大型解析/OCR/RAG 框架在第一步引入依赖安装、模型下载、性能和国产化兼容风险。

当前落地：

1. 自研 `POST /api/knowledge/documents` 入库接口，支持 PDF/TXT/Markdown。
2. 自研轻量 chunk 切分与 JSON 存储，运行期数据位于 `data/knowledge/`，测试通过 `APP_KNOWLEDGE_DIR` 隔离。
3. 入库 chunk 作为 `sourceType=document` 接入现有关键词检索，返回来源、页码、片段和命中原因。
4. PDF 解析器采取可选策略：未安装解析器时返回 `needs_parser`，扫描件返回或预留 `needs_ocr`，不阻断系统运行。

后续替换路线：

1. 文档解析优先评估 [Docling](https://github.com/docling-project/docling) 与 [MinerU](https://github.com/opendatalab/MinerU)，重点验证 PDF 到 Markdown/JSON 的结构保真、中文维修手册表现和 Windows/国产化部署成本。
2. OCR 优先评估 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)，重点验证中文扫描手册、故障图片和 PP-Structure 文档版面分析能力。
3. RAG ingestion 与索引编排后续评估 [LlamaIndex Ingestion Pipeline](https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/) 和 [LangChain RAG](https://docs.langchain.com/oss/python/langchain/rag)，但业务代码必须保留可替换边界，避免绑定单一框架。
4. 真正引入上述依赖前必须补充小样本验证记录：安装命令、解析效果、许可证、模型/依赖体积、离线演示可行性和 LoongArch/银河麒麟风险。
## 14. 多模态资料分析增强层落地记录

更新日期：2026-05-21。

本次实现新增自研 `multimodal_adapter`，用于把 PDF/图片资料分析结果转为本地可检索知识片段。该实现没有复制 OpenAI、Anthropic 或其他开源项目代码，也没有引入 PaddleOCR、MinerU、Docling、LlamaIndex、LangChain 等运行时依赖。

参考来源与工程边界：

1. OpenAI Responses API 的 PDF/图片输入能力用于后续真实 provider 适配参考。
2. Anthropic Claude PDF support 与 Vision Messages API 用于后续真实 provider 适配参考。
3. 当前默认 `mock` provider，确保无网络、无 API Key、官方国产化环境未开放时仍可完成比赛演示。
4. 官方 `摩托车发动机维修手册.pdf` 作为本地测试和演示资料，不提交到仓库。
5. 真实多模态调用存在 API Key、网络、费用、页数、文件大小和国产化环境兼容风险，比赛演示应保留 mock fallback。
