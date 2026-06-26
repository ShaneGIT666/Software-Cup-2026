# Target Environment Strict Audit Progress

## 2026-06-26

- Read the official problem baseline and software requirements documents.
- Rechecked prior open-source architecture and OCR research notes.
- Confirmed target VM evidence from previous deployment runs: LoongArch/Kylin Docker, real Qwen LLM, pypdf fallback success, Chroma install failure, MinerU unavailable.
- Added a pure Python JSON vector store in the previous local commit as the Chroma replacement for target delivery.
- Removed Chroma from default backend dependencies and made it optional through `backend/requirements-rag.txt`.
- Changed code defaults from Chroma to JSON vector store, then upgraded the target default to SQLite vector store.
- Created this audit tracking set: `task_plan.md`, `findings.md`, and `progress.md`.
- Researched mature Chroma replacements against primary sources. Current recommendation: SQLite vector index for delivery, JSON vector index as fallback, pgvector as P1 target-verified upgrade, sqlite-vec as P2 embedded experiment, Qdrant/Milvus/Weaviate excluded from the main route until LoongArch/Kylin proof exists.
- Added a dedicated Chroma non-compatibility conclusion: the blocker is `chroma-hnswlib` native dependency/wheel coverage and observed LoongArch build failure, not Chroma's product maturity.
