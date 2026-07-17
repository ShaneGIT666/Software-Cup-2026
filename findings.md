# Target Environment Strict Audit Findings

## Hard Requirement

The official A1 problem requires deployment on LoongArch CPU and Kylin server OS. This is not a bonus item. If a dependency cannot run there, it cannot be part of the delivery main route.

## Verified On Target Environment

- LoongArch/Kylin Docker route works with the Loongnix Python 3.11 base image.
- FastAPI backend, Vue static frontend hosting, JSON store, health/status APIs, search, RAG answer, and upload/review flows run in the container.
- The real OpenAI-compatible Qwen LLM endpoint works from the VM and returns non-mock RAG answers.
- `pypdf` works after being added to the default backend dependencies, so PDF text fallback closes the target upload path.

## Not Verified Or Failed On Target Environment

- Chroma is not target-safe as a default dependency. `chromadb` / `chroma-hnswlib` failed installation on loongarch64, so the main vector store has been replaced by the built-in SQLite vector index. The pure Python JSON vector index remains a fallback.
- MinerU is not available in the current target VM. The adapter can remain, but MinerU cannot be claimed as a target-running dependency until installed and verified there.
- Container-level Tesseract installation is not safe by default in the current Loongnix apt environment. Host Tesseract exists, but Docker delivery cannot depend on it.
- RapidOCR/PaddleOCR/ONNX-style OCR stacks are optional research routes until target installation and smoke tests pass.
- Local LLM runtimes are not part of the target main route unless a target-hosted service is provided and verified. Cloud/OpenAI-compatible Qwen is the verified model route.

## Mature Open-Source Patterns To Reuse

- RAGFlow: document ingestion state, evidence traceability, review-before-indexing, and parser artifact contracts.
- Haystack: componentized retrieval pipeline boundaries without adopting the runtime dependency.
- LlamaIndex: metadata-rich chunks, document nodes, and citation-aware retrieval models.
- Qdrant: payload-filtered vector retrieval design; the service itself is not a default dependency until target-verified.
- Dify, FastGPT, Open WebUI: provider configuration, model status visibility, and knowledge-base operations.
- Ragas and DeepEval: retrieval evaluation metrics and case-based regression testing, implemented locally in lightweight form.
- MinerU, Docling, PaddleOCR, RapidOCR: parsing/OCR capability references only; they must pass target-environment validation before becoming deliverable dependencies.

## Route Corrections

- Default vector search is now `RAG_VECTOR_STORE=sqlite`, not Chroma.
- `chromadb` is removed from default backend dependencies and moved to optional RAG dependencies.
- Docker defaults keep optional native-heavy features off unless explicitly enabled.
- Any new feature must first state its LoongArch/Kylin dependency evidence before entering the main delivery route.

## Vector Database Replacement Shortlist

- Keep now: built-in SQLite vector index. It uses Python stdlib `sqlite3`, is already integrated, and does not depend on native wheels.
- Fallback: built-in JSON vector index. It is pure Python and remains useful if SQLite is unavailable.
- Best mature replacement candidate: PostgreSQL + pgvector. It is mature, ACID, supports exact/approximate nearest neighbor search, and builds from source as a PostgreSQL extension. It must still pass LoongArch/Kylin installation before becoming a main-route dependency.
- Best embedded candidate: sqlite-vec. It is a single C extension that can be compiled for different platforms and fits single-machine contest delivery, but it is less mature and still must pass target compilation.
- Not a main-route candidate: Qdrant, because official installation requirements list amd64 and arm64 but not LoongArch.
- Not a two-day target route: Milvus and Weaviate. Both are mature, but their official deployment paths are heavy Docker/service stacks and need architecture-specific verification before use.

## Chroma Non-Compatibility Conclusion

Chroma is not rejected because it is weak; it is rejected as the default target dependency because its native HNSW dependency chain does not currently install on the LoongArch/Kylin Docker target. `chroma-hnswlib` provides wheels for x86-64 and ARM64 style platforms, but not LoongArch. In our VM tests, both modern `chromadb>=0.5,<2` and pinned `chromadb==0.5.23` failed during dependency build, including `chroma-hnswlib`. Since this blocks Docker image build, Chroma can only remain optional. The default replacement is SQLite vector index, with JSON vector index as fallback.

## Final Submission Code Findings

- `/api/multimodal/diagnosis` already calls `analyze_ocr_document()` and `analyze_multimodal_document()`, then appends OCR text and image clues into `expandedFaultText` before calling `diagnose_with_rag()`.
- Existing multimodal response includes `queryContext.imageClues`, `queryContext.ocrText`, `imageAnalysis`, `results`, `citations`, and `evidencePack`, but it does not yet expose a formal `multimodalSignals` object or annotate citations with `crossModalMatchMode`.
- Existing tests already enforce that image clues enter the diagnostic request and are not promoted to formal evidence. The new work should extend this rather than changing the core retrieval or Evidence Pack contract.
- There is no existing RAG feedback / corrected-answer API. The safest implementation is a JSON-backed service that defaults feedback to `pending_review`, exposes review endpoints, and only adds approved feedback to the lightweight knowledge graph, not to formal RAG retrieval.

## Full Trust Hardening Findings

- The 2026-07-11 hardening plan requires strict T00 baseline protection before functional changes.
- Current branch at start was `main`; hardening work moved to `codex/full-trust-hardening-20260711`.
- The worktree was already dirty before hardening: `data/examples/repair-cases.json` modified and `tmp/` untracked. These are preserved as user changes.
- Baseline targeted backend tests passed: `21 passed in 2.70s`.
- Baseline frontend build passed. Existing build warnings are Rollup/Vite annotation and chunk-size warnings, not hard failures.
- The local shell does not expose `python` on PATH, but `backend/.venv/Scripts/python.exe` works and should be used for project scripts.

## 2026-07-14 LoongArch Acceptance Closure Findings

- Starting branch is `codex/fix-auth-management-runtime-20260714`; the only dirty paths are preserved user content in `data/examples/repair-cases.json` and `tmp/`.
- Existing target evidence reaches `TARGET_CORE_GO`, not final `GO`.
- Known unresolved hard gates are real repair-image multimodal verification and target Docker daemon availability.
- Current final-submission documentation also records local Pydantic 1 compatibility and local engineering NO-GO states; these must be rerun against the current branch before deciding whether they remain valid.
- The public target endpoint fingerprints match the locally trusted RSA and ED25519 fingerprints; the first SSH failure was sandbox access to `known_hosts`, not a changed target identity.
- Live target audit reconfirmed `loongarch64` and Kylin V11. The official manual exists, but no real JPG/PNG acceptance image exists in the target home tree.
- `pdftoppm` was missing and sudo is unavailable. The official Kylin `poppler-utils-23.12.0-7.p04.ky11.loongarch64` RPM was downloaded and unpacked to the target user's local directory; `pdftoppm 23.12.0` now runs without changing the system package database.
- The target cannot access GitHub HTTPS, and its user Git lacks the HTTPS helper. After explicit user approval, only committed public history was transferred by Git bundle into a new isolated target worktree.
- The acceptance harness required two target-derived fixes: safely loading `.env` only inside the real-provider/manual probe subshell, and allowing the documented MinerU disabled/failed/unavailable fallback reasons in the API contract test.
- At accepted SHA `d47ea9b`, the real provider and three-page official-manual multimodal flow passed with 3/3 real pages and zero fallbacks; strict target backend tests passed 327 tests and the frontend production build passed.
- Docker CLI 24.0.9 is installed, but the daemon is inactive and `/var/run/docker.sock` is absent. Docker remains `OPTIONAL_UNVERIFIED`; the verified main route is venv + FastAPI static hosting.

## 2026-07-17 Final Acceptance Closure Findings

- Final acceptance starts from branch `codex/fix-auth-management-runtime-20260714` at local HEAD `c7963a4`.
- The only pre-existing dirty paths remain user-owned `data/examples/repair-cases.json` and `tmp/`.
- Existing records prove LoongArch `LOONGARCH_MULTIMODAL_GO` / `TARGET_CORE_GO`, but the submission gate still reports `FINAL_SUBMISSION_NO_GO` because human visual review and older local compatibility/engineering states have not been reconciled against current evidence.
- GitHub HTTPS remains unstable: the 2026-07-17 read-only remote query reset, so remote synchronization cannot yet be claimed.
- Repository-defined final gate currently has three stated blockers: stale local Pydantic 1 evidence, at least 10 human-reviewed visual pages, and optional Docker revalidation; LoongArch venv acceptance is already GO.
- The human review package exists at `tmp/manual-visual-human-review/` with 20 page images and a 20-row CSV, but every `human_result` is blank. Machine evidence alone cannot satisfy the explicitly human gate.
- The Pydantic compatibility test is a focused four-case schema suite and can be rerun in an isolated Pydantic 1 environment on the current Python runtime; the LoongArch target already passed the full suite under Pydantic 1.10.26.
- Several historical documents claim an earlier Docker success, while the current acceptance target reports an inactive daemon and absent socket. Final reporting must distinguish historical Docker evidence from current-SHA Docker acceptance.
- The current branch full backend suite passes all 327 tests locally; the stale `LOCAL_FINAL_ENGINEERING_NO_GO` statement is no longer supported by current evidence.
- The formerly blocked local compatibility gate is now closed: Python 3.12.13 + Pydantic 1.10.26 passed `tests/test_pydantic_compat.py` (4/4), matching the target's Pydantic 1 runtime evidence.
- `production_readiness_check.py` is sensitive to ambient auth configuration and needs explicit isolated acceptance variables; its first current run failed closed with the intended actionable 503 rather than an application exception.
- Readiness passes completely when run under its intended isolated test/off authentication variables; this closes the earlier false-negative configuration state.
- Secret scan's only tracked application/script match is the shell code that writes freshly generated token variables, not a literal credential.
- The machine visual audit commit `b1a0d193...` is an ancestor of current HEAD, and the local official manual SHA256 matches the recorded `aad3c072...`; current tests cover the subsequently committed audit script.
- No human review decisions have appeared since the machine audit. Final human GO remains a user/reviewer attestation requirement, not a reproducible code defect.
- A fresh 2026-07-17 target run independently reproduces the earlier LoongArch result at application SHA `d47ea9b`: real multimodal 3/3, backend 327/327, frontend build, auth/API/manual/real-text provider, and outer `LOONGARCH_MULTIMODAL_GO` all pass.
- The only current final-submission hard blocker is the explicit human visual attestation. Docker is an optional route under repository policy and remains accurately unverified on the current target because its daemon is inactive.
- Final documentation contained two stale limitations (245-test Pydantic count and CRLF init script); current git EOL metadata and fresh validation close both.
