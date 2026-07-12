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
- Completed T07/T08: case creation now preserves caller-provided `deviceType`, `riskLevel`, `maintenanceLevel`, and workflow selection; missing workflow uses the closest existing workflow instead of a hardcoded route.
- Added minimal role protection in token mode through `backend/app/auth.py`; reviewer/admin routes are protected when `AUTH_MODE=token`, while `AUTH_MODE=off` keeps the local demo path unchanged.
- Added `.env.example` auth variables: `AUTH_MODE`, `AUTH_TOKEN`, `AUTH_TOKEN_ROLE`, `AUTH_REVIEWER_TOKEN`, and `AUTH_ADMIN_TOKEN`.
- Backend API contract tests passed after T07/T08: `97 passed in 15.49s`.
- Combined retrieval/evidence/chunk/graph/multimodal/corrective/safety/case regression passed after T07/T08: `30 passed in 1.03s`.
- Addressed review-blocking validation before continuing T09-T15.
- Hardened token auth with `secrets.compare_digest`, an explicit operator token, 401 for missing/malformed/invalid tokens, and 403 for insufficient roles.
- Added auth status visibility to provider status without exposing configured token values, including warnings for `AUTH_MODE=off` and missing reviewer/admin tokens in token mode.
- Removed the public `/knowledge` static mount and kept file-like SPA fallbacks at 404.
- Added frontend `Authorization: Bearer ...` injection from `localStorage.softwareCupAuthToken` or `VITE_API_AUTH_TOKEN`.
- Added role-matrix, auth-status, token-leak, and `/knowledge` static exposure tests.
- Added final search source coverage so an approved case with a strong keyword hit is not pushed out of the requested topK by document results that appear in both keyword and vector channels.
- Fixed motorcycle manual test helpers so simulated approval marks chunks current, and adjusted visual asset source assertions to accept page-specific source names.
- Affected backend regression passed: `135 passed in 44.85s`.
- Required full backend suite passed with `MINERU_ENABLED=false`: `188 passed in 44.79s`.
- Frontend production build passed after auth header injection: `built in 5.05s` with existing Vite/Rollup warnings.
- Started R01-R08 review-blocker closure on branch `codex/full-trust-hardening-20260711` at `e9d1303`; preserved existing user changes in `data/examples/repair-cases.json` and `tmp/`.
- R01 closed knowledge revision state gaps: only current approved chunks can be revised, duplicate pending proposals are rejected, stale proposal approval fails with 409, status transitions are explicit, revision review fields sync on approve/reject, and a logical chunk can have only one current approved version.
- R01 targeted regression passed: `10 passed in 1.11s` across chunk revision audit, approved-only knowledge graph, and evidence pack tests.
- R02 replaced broad case coverage promotion with an explicit source diversity policy: only approved, strong keyword/matched-term cases with comparable rerank/fusion score can replace the final topK item; weak vector-only, low-score, small-topK, and already-covered cases are not promoted.
- R02 targeted retrieval regression passed: `17 passed in 0.41s`.
- R03 completed repair case metadata and workflow selection: `component` and `faultCode` are accepted, stored, and returned in approved case search results; explicit workflow IDs are validated for existence and device compatibility; no reliable match now stores `workflowId=null` with `workflowSelectionReason=no_reliable_match` instead of falling back to the first workflow.
- R03 frontend case submission now supports device type, component, fault code, risk level, maintenance level, and optional workflow ID.
- R03 validation passed: backend `120 passed in 14.32s`; frontend build passed in `5.34s` with existing Vite/Rollup warnings.
- R04 completed the role-based API authorization matrix: token mode now rejects unsupported `AUTH_MODE`, invalid `AUTH_TOKEN_ROLE`, duplicate cross-role tokens, and missing admin token; operator submission routes, reviewer review/list routes, and admin validation/maintenance routes are explicitly protected.
- R04 status reporting exposes auth booleans and redacted configuration errors without token material.
- R04 backend validation passed: `105 passed in 14.37s`.
- R05 added controlled knowledge document file access at `/api/knowledge/documents/{document_id}/file` with reviewer authorization, fixed new and returned document URLs to use the controlled API, and kept the old public `/knowledge` path inaccessible.
- R05 frontend document opening now fetches the controlled file endpoint with Authorization headers and opens a blob URL instead of using a raw public link.
- R05 validation passed: backend `106 passed in 14.41s`; frontend build passed in `5.48s` with existing Vite/Rollup warnings.
- R06 removed frontend build-time API token configuration, switched browser credentials to `sessionStorage.softwareCupAuthToken`, exported token session helpers and `ApiRequestError`, and added a status-page token save/clear UI that never displays the token value.
- R06 validation passed: frontend build passed in `5.29s`; build artifact scan for `VITE_API_AUTH_TOKEN|operator-token|review-token|admin-token` returned no matches.
- R07 enforced grounded RAG answer semantics: no-evidence LLM fallback now defaults to disabled, citations and evidence default missing review state to `unknown`, non-approved evidence is fail-closed with no repair steps, and final answer metadata now distinguishes `rawAnswer`, `answer`, `llmAnswerUsed`, `llmCandidateAccepted`, `finalAnswerSource`, and `answerMode`.
- R07 validation passed: backend RAG/evidence/corrective/safety regression `119 passed in 12.04s`.
- R08 final validation: removed the dead `RAG_REQUIRE_GROUNDED_REPAIR_STEPS` sample setting because runtime code does not read it; full backend suite passed `205 passed in 50.39s`, affected regression passed `146 passed in 12.91s`, and frontend production build passed in `5.81s` with only existing Rollup annotation/chunk-size warnings.
- R08 regression closure: strong approved cases may use a comparable keyword score when document vector/RRF scores dominate, while weak vector-only and low-score cases remain ineligible for diversity promotion; focused verification passed `42 passed in 36.14s`.
- R08 artifact secret scan returned no matches; `git diff --check` passed; `data/examples/repair-cases.json` and `tmp/` remain uncommitted user content. T09-T15 remains pending.
- Started post-R08 review closure H01-H02. T09-T15 remains pending.
- H01 completed: uploaded fault artifacts now use operator-protected file access; public /uploads paths return 404; review status summaries default missing states to unknown and exclude them from approved/retrievable counts.
- H02 completed: source diversity promotion now requires an RRF/rerank score floor, and RAG answerMode now follows Corrective RAG outcomes with grounded, grounded_with_caution, and insufficient_evidence states.
- Post-R08 review closure validation: full backend suite passed 211 tests in 48.62s; affected regression passed 154 tests in 12.90s; frontend production build passed in 5.22s; artifact credential scan returned no matches; public /uploads and /knowledge paths remain unavailable; user-owned data/examples/repair-cases.json and tmp/ remain uncommitted; T09-T15 remains pending.
- Secure delivery auth closure: default delivery configuration now uses competition/token mode; AUTH_MODE=off is only available with an explicit local unsafe flag and is forbidden for competition, production, and submission environments. Both init-config scripts generate masked random role tokens by default and reserve unsafe mode for loopback-only demos.
- Document status closure: mixed terminal, empty, unknown, and non-current approved chunk sets no longer retain indexed status; currentApprovedCount is recorded.
- Diagnosis contract closure: /api/rag/answer, /api/diagnosis, and /api/multimodal/diagnosis now consistently expose answerMode and LLM source fields after corrective and safety processing.
- Retrieval verification: low-score approved cases are not promoted into topK, while exact queries with the maximum supported topK still retrieve approved cases; result summaries now describe RRF fusion.
- Post-H02 audit validation: first targeted backend suite passed 122 tests in 12.64s; second targeted backend suite passed 166 tests in 50.12s; full backend suite passed 220 tests in 50.52s; affected regression passed 179 tests in 58.85s; frontend build passed in 5.72s; credential scans found no real tokens (only test fixtures and documentation placeholders); user-owned data/examples/repair-cases.json and tmp/ remain uncommitted; T09-T15 remains pending.
- Follow-up audit found that the Linux init script used non-expanding/escaped AUTH_LINES output and emitted a Windows venv path. The Linux delivery claim was therefore reopened and fixed with behavioral shell tests before hardening acceptance.
