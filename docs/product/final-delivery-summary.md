# 最终交付摘要

## 交付定位

本项目面向中国软件杯 A1 赛题，交付形态是可在 PC Web 访问、可在 LoongArch/银河麒麟目标环境部署的“设备检修知识检索与作业辅助系统”准生产级原型。

本轮最终收口不再扩大功能边界，重点保证以下主链路可以演示和答辩：

1. 资料上传进入解析链路，解析产物默认进入 `pending_review`。
2. 审核通过后才进入正式检索索引，`pending_review/rejected/deprecated/replaced` 不参与 RAG。
3. 文本、OCR、多模态/图片资产分析结果都沉淀为可审核知识片段。
4. `/api/search` 返回关键词与向量检索结果，并保留 `chunkId/sourceDocId/page/section`。
5. `/api/rag/answer` 基于 Evidence Pack 输出结构化检修建议，证据不足时明确“不确定”。
6. 真实 LLM 使用 OpenAI-compatible provider 接入，mock/offline 仅作为现场兜底。
7. 目标环境默认使用 SQLite 向量索引，sqlite-vec/Qdrant/Chroma 作为可选增强，失败时回退本地索引。

## 核心能力

| 能力 | 当前交付状态 |
| --- | --- |
| PC Web 可视化 | Vue 3 + Element Plus，支持检索、RAG、资料入库、审核、系统状态展示 |
| 文档解析 | parser router + MinerU adapter；MinerU 不可用时降级普通解析/mock parser |
| 图片资产解析 | MinerU assets 自动触发 OCR/多模态/文本 LLM 兜底分析，产物进入 pending_review |
| 审核状态机 | `draft/pending_review/approved/rejected/deprecated/replaced` |
| 检索隔离 | 默认只检索 `approved` 知识片段 |
| Evidence Pack | 保留 evidence id、chunk id、source doc id、page、section、retrievalSource、scoreBreakdown |
| RAG 输出 | 固定为初步判断、检查步骤、维修步骤、安全提醒、验收标准、引用证据、不确定信息 |
| 真实 LLM | 支持 OpenAI-compatible 服务；比赛 Qwen 服务通过 `.env` 配置，不提交 Key |
| 向量索引 | 默认 SQLite + hash/openai-compatible embedding；LoongArch Docker 已验证 SQLite 可运行 |
| 可选增强 | sqlite-vec、Qdrant、Chroma 均为可选入口，不作为比赛环境硬依赖 |

## 部署策略

比赛环境采用 Docker 优先：

```bash
docker build -t software-cup-demo:final .
docker run --rm -p 8000:8000 --env-file .env software-cup-demo:final
```

默认生产兜底配置：

```env
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
OCR_PROVIDER=mock
RAG_VECTOR_STORE=sqlite
RAG_VECTOR_SQLITE_ENGINE=python_scan
RAG_VECTOR_ENHANCER=off
RAG_VECTOR_FALLBACK_LOCAL=on
MINERU_ENABLED=false
```

真实模型演示时打开：

```env
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_BASE_URL=<competition-compatible-base-url>
OPENAI_MODEL=<competition-chat-model>
OPENAI_API_STYLE=chat_completions
OPENAI_API_KEY=<secret>
```

## 交付边界

- 不提交 `.env`、API Key、上传运行数据、`node_modules`、`.venv`、`frontend/dist`。
- Chroma 不再作为 LoongArch 主链路依赖，原因见 `docs/research/loongarch-vector-db-alternatives-2026-06-26.md`。
- hash embedding 只作为 fallback，不宣传为真实语义 embedding。
- sqlite-vec 和 Qdrant 已预留可选入口；若目标环境现场无法安装，系统仍以 SQLite Python scan 跑完整闭环。

