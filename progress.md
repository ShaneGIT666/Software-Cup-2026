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

## 2026-07-11 Full trust hardening

- Read the external full-trust hardening execution plan from `E:/Download/Downloads/Software-Cup-2026_GPT-5.5-High_Agent全量整改执行计划.md`.
- Ran starting git checks in `E:/Software/Software-Cup-2026`: branch `main`, HEAD `09f9b3a0cd485e12b51a289996f4e3a44e0ae542`, dirty worktree with `data/examples/repair-cases.json` and `tmp/`.
- Created hardening branch `codex/full-trust-hardening-20260711` without stashing, resetting, cleaning, or overwriting existing changes.
- Confirmed runtimes: `backend/.venv/Scripts/python.exe` is Python `3.12.13`, Node `v24.15.0`, npm `11.12.1`; system `python` is not on PATH.
- Ran T00 targeted backend baseline tests: `21 passed in 2.70s`.
- Ran T00 frontend production build: passed in `5.88s` with existing Vite/Rollup warnings.
- Added `docs/project-management/full-trust-hardening-baseline.md` and appended this hardening task set to the persistent planning files.
- Completed T01/T02 retrieval hardening: `fusion_score` is now the first RRF sort key, score breakdown records `scoreKind=rrf_display`, RRF K is configurable with invalid-value fallback, and search expands to a configurable candidate pool before rerank and final `topK` clipping.
- Updated retrieval tests to cover RRF-over-keyword ordering, three-route RRF accumulation, duplicate chunk merge, single-route stability, `top_k` formula independence, invalid `RAG_RRF_K`, and candidate-pool rerank recovery.
- Targeted retrieval test passed: `12 passed in 0.44s`.
- Expanded T00-related backend regression passed after retrieval changes: `26 passed in 0.62s`.
- `git diff --check` passed with only CRLF conversion warnings.
- Completed T03/T04 knowledge governance: chunk revision now creates a pending version with `logical_chunk_id`, incremented `version`, `supersedes`, and `is_current=false`; approving that version marks the old chunk `replaced`, sets `replaced_by`, and syncs only the current approved chunk.
- Added `backend/app/review_policy.py` and changed retrieval/vector/graph/review paths so missing review metadata normalizes to `unknown` instead of defaulting to `approved`.
- Updated API and focused tests for pending revisions, approved replacement, rejected revisions, graph approved-only isolation, candidate-pool vector recall, and explicit approved vector sync fixtures.
- T03/T04 targeted tests passed: `3 passed in 0.82s`.
- Backend API contract tests passed after update: `95 passed in 14.54s`.
- Combined retrieval/evidence/chunk/graph/multimodal/corrective/safety regression passed: `28 passed in 0.74s`.
- Completed T05/T06 RAG answer safety: removed post-safety restoration of raw LLM text, kept provider text only in `rawAnswer`, and made safety/corrective structured output the final `answer`.
- Evidence-empty structured output now has no `repairSteps`; Corrective RAG also clears repair steps and refreshes `recommendedActions` when action is `needs_more_evidence`.
- T05/T06 focused tests passed: `11 passed in 0.21s`.
- Backend API contract tests passed after T05/T06: `95 passed in 14.66s`.
- Combined retrieval/evidence/chunk/graph/multimodal/corrective/safety regression passed after T05/T06: `28 passed in 0.76s`.
