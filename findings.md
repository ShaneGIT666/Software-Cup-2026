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
