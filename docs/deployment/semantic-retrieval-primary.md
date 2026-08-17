# 语义检索主方案：SQLite Vector Store + Embedding

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 当前结论

LoongArch/Kylin 比赛交付主链路不再使用 ChromaDB 作为默认向量数据库。目标环境实测中，`chromadb` / `chroma-hnswlib` 原生依赖在 loongarch64 上构建失败，会阻塞 Docker image 构建。

当前默认方案：

```env
RAG_VECTOR_STORE=sqlite
APP_VECTOR_DB_PATH=./data/knowledge/vector-index.sqlite3
RAG_EMBEDDING_PROVIDER=hash
```

说明：

- `RAG_VECTOR_STORE=sqlite`：启用内置 SQLite 向量索引，只同步 `review_status=approved` 的知识片段。
- `pending_review`、`rejected`、`deprecated`、`replaced` 不进入正式向量索引。
- SQLite 后端使用 Python 标准库 `sqlite3`，不需要额外 Python wheel、Docker sidecar 或外部数据库服务。
- 查询阶段当前采用线性 cosine 扫描，适合比赛和单机演示规模；后续可升级 pgvector 或 sqlite-vec。
- `RAG_VECTOR_STORE=json` 保留为更小的纯文件 fallback。
- `RAG_VECTOR_STORE=chroma` 只允许在已验证 `chromadb` 可安装的非 LoongArch 环境使用。

## 检索流程

```text
资料上传 / OCR 文本 / 多模态分析结果
-> 切分为 document chunks
-> pending_review
-> 人工审核为 approved
-> embedding provider 生成向量
-> SQLite vector store 持久化索引
-> /api/search 召回：关键词结果 + SQLite 向量结果
-> /api/rag/answer 引用召回片段生成回答
```

## Provider 配置

默认目标环境配置：

```env
REMOTE_API_MODE=auto
RAG_VECTOR_STORE=sqlite
RAG_EMBEDDING_PROVIDER=hash
```

真实 embedding 可选增强：

```env
REMOTE_API_MODE=auto
RAG_VECTOR_STORE=sqlite
RAG_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://your-compatible-provider/v1
OPENAI_EMBEDDING_MODEL=your-provider-embedding-model
```

注意：

- `text-embedding-3-small` 只是 OpenAI 官方模型示例。
- DashScope/Qwen、SiliconFlow 或其他 OpenAI-compatible provider 必须填写各自真实 embedding 模型名。
- 如果 embedding API 不可用，系统会自动回退 hash embedding，不中断上传、审核、检索和 RAG。

## 答辩口径

系统采用目标环境优先的混合检索架构。设备型号、故障码、部件名优先通过关键词和字段权重召回；语义描述通过内置 SQLite 向量索引召回已审核知识片段。所有自动解析和多模态分析产物默认进入 `pending_review`，审核通过后才会同步到正式检索索引。

ChromaDB 仍保留为可选兼容路径，但由于其原生 HNSW 依赖在 LoongArch/Kylin 当前环境无法可靠安装，不能作为比赛主交付依赖。后续生产级增强优先验证 PostgreSQL + pgvector，其次验证 sqlite-vec。

## 风险边界

- SQLite 向量索引是目标环境可运行的嵌入式方案，不等同于大规模 ANN 服务。
- hash embedding 只能称为 fallback，不应宣传为真实语义 embedding。
- 真实 embedding 模型只有在 provider、model、base_url、API key 都验证通过后才能作为演示口径。
- Chroma、Qdrant、Milvus、Weaviate、pgvector、sqlite-vec 进入主链路前，都必须先通过 LoongArch/Kylin 安装和接口冒烟。
# 最终语义检索主方案（交付版）

比赛目标环境采用 `SQLite vector store + approved-only indexing` 作为默认主链路：

```env
RAG_VECTOR_STORE=sqlite
RAG_VECTOR_SQLITE_ENGINE=python_scan
RAG_VECTOR_ENHANCER=off
RAG_VECTOR_FALLBACK_LOCAL=on
```

可选增强：

```env
# sqlite-vec，本地扩展可用时启用；不可用自动回退 python_scan
RAG_VECTOR_SQLITE_ENGINE=sqlite_vec
SQLITE_VEC_EXTENSION_PATH=/path/to/sqlite-vec

# Qdrant，服务可用时作为增强召回；不可用自动回退 SQLite
RAG_VECTOR_ENHANCER=qdrant
RAG_QDRANT_URL=http://127.0.0.1:6333
RAG_QDRANT_COLLECTION=repair_knowledge_chunks
RAG_VECTOR_FALLBACK_LOCAL=on
```

Chroma 仅作为兼容路径，不作为 LoongArch/银河麒麟交付硬依赖。原因是 `chromadb/chroma-hnswlib` 等原生依赖在 loongarch64 上缺少稳定 wheel，现场 Docker 构建风险高。

---
