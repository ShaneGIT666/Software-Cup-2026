# 答辩 Q&A

## 为什么没有把 ChromaDB 作为 LoongArch 主链路？

ChromaDB 依赖 `chromadb/chroma-hnswlib` 等原生组件。目标 LoongArch/银河麒麟环境中 wheel 和源码构建不稳定，会阻塞 Docker 镜像构建和现场部署。比赛交付优先保证目标环境完整闭环，因此主链路改为 Python 标准库可用的 SQLite 向量索引。

Chroma 仍保留为可选兼容路径，在非 LoongArch 或已验证可安装环境可打开。

## SQLite 向量索引是否足够生产级？

当前交付是准生产级原型。SQLite 方案优点是单机可部署、无额外服务、LoongArch 可运行、方便审核隔离和现场演示。它不等同于大规模 ANN 服务。后续生产增强路线是：

1. sqlite-vec：仍保持单机嵌入式，但需要 LoongArch 扩展构建验证。
2. Qdrant：作为独立向量服务增强，需验证 LoongArch 镜像或源码构建。
3. PostgreSQL + pgvector：适合企业级数据管理，但两天交付期不迁移数据库。

## 如何保证 pending_review 不污染 RAG？

解析、OCR、多模态和人工上传案例默认进入 `pending_review`。索引同步函数只同步 `review_status=approved` 的片段；检索和 Evidence Pack 也只使用 approved。拒绝、废弃、替换状态不进入正式检索。

## LLM 会不会编造检修参数？

RAG prompt 和结构化输出要求所有建议基于 evidence。Evidence Pack 保留 `chunkId/sourceDocId/page/section`。证据不足时输出“不确定信息”，高风险 evidence 触发人工复核提醒。

## MinerU 与图片资产增强的价值是什么？

维修手册包含大量图表、线路图、爆炸图和步骤截图。MinerU 负责从 PDF/Office 中抽取文本与 assets；系统随后对图片 assets 进行 OCR、视觉分析或 OCR + 文本 LLM 兜底总结，把图片信息变成可审核知识片段，避免只解析正文导致信息缺失。

## 真实 LLM 如何接入？

系统使用 OpenAI-compatible adapter。比赛提供的 Qwen 服务只需要配置 `OPENAI_BASE_URL/OPENAI_MODEL/OPENAI_API_KEY/OPENAI_API_STYLE=chat_completions`，不改代码。Key 只放 `.env`，不进入仓库。

## fallback 是否会影响真实性？

fallback 是现场稳定性设计，不作为真实模型能力宣传。答辩时明确区分：

- 真实 LLM：用于演示智能回答。
- hash embedding：用于网络或 embedding 服务不可用时的检索兜底。
- mock OCR/LLM：用于离线可启动和弱网兜底。

