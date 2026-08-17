# Target Environment Strict Audit Progress

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](README.md)、[软件需求规格说明书](docs/requirements/software-requirements-spec.md)和[修改日志索引](docs/change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

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

## 2026-06-27 Final submission closure

- Read the new final pre-submission goal from `C:\Users\liuzi\.codex\attachments\97808d9d-d84b-46be-92dc-ea9e9b955144\pasted-text.txt`.
- Ran starting checks: branch `main...origin/main`, latest commit `952e5a9 finalize delivery verification docs`, worktree clean at task start.
- Planning catchup first failed because `python` is not on PATH; reran successfully with `backend/.venv/Scripts/python.exe`.
- Appended the final submission closure goal and step list to `task_plan.md`.
- Inspected backend API, schema, RAG, evidence pack, knowledge graph, services, data store, frontend API/components, and existing key tests.
- Added RAG feedback schemas, JSON store helpers, service functions, FastAPI endpoints, review-workbench visibility, and approved-only knowledge graph nodes.
- Added explicit `multimodalSignals` and cross-modal score breakdown annotations to `/api/multimodal/diagnosis`, with OCR/vision exception fallback.
- Added frontend display for cross-modal signals and a minimal RAG answer feedback/correction form.
- Added `tests/test_multimodal_cross_modal_signals.py` and `tests/test_rag_feedback_review_flow.py`.
- Targeted new tests passed: `6 passed in 0.51s`.
- Key contest chain tests passed: `15 passed in 0.70s` across multimodal, cross-modal signals, RAG feedback, maintenance guidance, case review, chunk revision, approved-only graph, and official smoke tests.
- Full backend test suite passed: `174 passed in 729.77s`.
- Frontend production build passed: `built in 4.65s`.
- Readiness passed: `success=true`, duration `579.92ms`.
- JSON maintenance passed: `success=true`, `fileCount=4`, `issueCount=0`.
- API smoke passed with temporary runtime directories: health/status/search/RAG/multimodal/RAG feedback/graph all returned expected results.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `python` not found on PATH | Planning catchup | Used `backend/.venv/Scripts/python.exe` |
| Looked for `frontend/src/style.css` | Frontend style inspection | Corrected to `frontend/src/styles.css` |
| Cross-modal signal test expected raw `OCR_LOW_FUEL_PRESSURE`, code split it into tokens | First targeted test run | Preserved raw image/OCR signal strings in `matchedQueryTerms` |
| API smoke `POST /api/rag/feedback` returned 500 | First smoke run used repository `data/knowledge` runtime directory | Restarted uvicorn with temporary `APP_EXAMPLES_DIR`, `APP_KNOWLEDGE_DIR`, and `APP_UPLOAD_DIR`; smoke passed |
