# 语义检索主方案：Embedding + ChromaDB

本项目将“真实 embedding 模型 + ChromaDB 向量数据库”设为资料知识片段的语义检索主方案，用于提升已审核检修手册、OCR 文本和故障图片分析结果的语义召回能力。关键词检索仍承担设备型号、故障码、部件名和维修案例召回，hash embedding 只作为无 Key、弱网、依赖不可用时的兜底链路。

## 默认配置

```env
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_API_STYLE=openai_compatible
EMBEDDING_TIMEOUT_SECONDS=20
```

说明：

- `RAG_VECTOR_STORE=chroma`：启用 Chroma collection；只有 `review_status=approved` 的资料知识片段会同步，`pending_review` 不进入正式索引。
- `RAG_EMBEDDING_PROVIDER=openai`：通过 OpenAI-compatible `/embeddings` 接口生成真实语义向量，实际复用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。
- `text-embedding-3-small` 只对应 OpenAI 官方接口默认示例；DashScope/Qwen、SiliconFlow 或其他兼容网关必须填写该 provider 自己的 embedding 模型名，不能把它当作通用旧名或别名。
- 如果未配置 Key、`REMOTE_API_MODE=off`、embedding 服务失败或 Chroma 初始化失败，系统会自动回退到 hash embedding 或关键词检索，接口不崩。

## 云端模型示例

```env
REMOTE_API_MODE=auto
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

## 国产 / OpenAI-Compatible 示例

可使用支持 `/embeddings` 的 Qwen、SiliconFlow、LiteLLM 网关或其他兼容服务：

```env
REMOTE_API_MODE=auto
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://your-compatible-provider/v1
OPENAI_EMBEDDING_MODEL=your-embedding-model
```

## 本地模型示例

若本地服务提供 OpenAI-compatible `/embeddings`：

```env
REMOTE_API_MODE=auto
RAG_VECTOR_STORE=chroma
RAG_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=local-placeholder
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_EMBEDDING_MODEL=nomic-embed-text
```

## 检索流程

```text
资料上传/OCR 文本/多模态分析结果
-> 切分为 document chunks
-> pending_review
-> 人工审核为 approved
-> embedding 模型生成向量
-> ChromaDB 持久化索引
-> /api/search 混合召回：关键词结果 + Chroma 语义结果
-> /api/rag/answer 引用召回片段生成回答
```

## 答辩口径

系统采用混合语义检索架构。主路径使用 ChromaDB 向量数据库和可配置 OpenAI-compatible embedding 模型，实现已审核检修知识片段、OCR 文本和图片分析结果的语义召回；设备型号、故障码、部件名和维修案例继续由关键词/字段权重优先召回。兜底路径保留关键词检索与 hash embedding，确保离线、弱网或模型不可用时仍能完成演示。

## 风险边界

- hash embedding 只能称为 fallback，不应宣称为真实语义 embedding。
- 自动解析或模型分析结果默认 `pending_review`，审核通过前不会同步 Chroma。
- 当前维修案例进入检索主要依赖案例审核后的关键词/字段匹配；尚未同步为 Chroma 向量知识片段。
- LoongArch/Kylin 最小部署可显式设置 `RAG_VECTOR_STORE=off`，先保证前后端和 mock/RAG 演示链路稳定。
- ChromaDB 是单机 MVP 友好的向量库；若后续需要多租户、高并发或更强过滤检索，可升级到 Qdrant、Milvus 等服务型向量库。
