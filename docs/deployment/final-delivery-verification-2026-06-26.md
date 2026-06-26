# Final Delivery Verification, 2026-06-26

## Scope

This record captures the final delivery smoke test for the Software Cup prototype after the MinerU asset-analysis backend enhancement and delivery UI polish.

## Local Verification

- Backend full test suite with `MINERU_ENABLED=false`: `151 passed`.
- Frontend production build: passed.
- Production readiness check: passed.
- JSON store maintenance check: passed, `issueCount=0`.
- `git diff --check`: passed.

Known frontend build warnings:

- VueUse PURE annotation warnings from Rollup.
- Vite chunk size warning for the production bundle.

## LoongArch / Kylin Verification

Target environment:

- Architecture: `loongarch64`
- OS: `Kylin Linux Advanced Server V11 (Swan25)`
- Python: `3.11.6`
- Node: `v20.18.2`
- Docker: `24.0.9`

Docker build result:

- Image: `software-cup-demo:20260626`
- Base image: `cr.loongnix.cn/library/python:3.11`
- Build status: passed after making Chroma optional in the default Docker image.

Runtime configuration:

- `REMOTE_API_MODE=auto`
- `LLM_PROVIDER=openai`
- `OPENAI_BASE_URL` points to the competition MaaS OpenAI-compatible endpoint.
- `OPENAI_MODEL=xopqwen36v35b`
- `RAG_VECTOR_STORE=sqlite` for the target-compatible built-in SQLite vector index. Earlier smoke runs also verified the pure keyword path with `RAG_VECTOR_STORE=off`.
- `MINERU_ENABLED=true`
- `KNOWLEDGE_AUTO_ANALYZE_ASSETS=true`
- `OCR_PROVIDER=mock`

API key was only written to a temporary VM env file and was not committed.

## Smoke Results

Container health:

- `GET /api/health`: passed.
- `GET /api/providers/status`: passed.
- Frontend `GET /`: passed.

Provider status highlights:

- LLM effective provider: `openai`.
- LLM key configured: `true`.
- Vector-store status: SQLite vector index is the default target-compatible route. Chroma is optional and not required for the competition Docker image.
- MinerU status: `fallback`, because MinerU is enabled but not installed in the LoongArch container image.

Real LLM smoke:

- `POST /api/providers/llm/validate`: success, provider `openai`, model `xopqwen36v35b`, fallback `false`.
- `POST /api/rag/answer`: success, provider `openai`, model `xopqwen36v35b`, fallback `false`, citations `3`, evidence pack present.
- The RAG answer returned a standard heading-style response. The backend marked `llmAnswerUsed=false` with `llmAnswerMode=missing_required_headings`, so the delivery demo should describe this as "real LLM result available with guarded structured-answer adoption."

Knowledge ingestion smoke:

- Uploaded `software-cup-smoke-manual.md` through `/api/knowledge/documents/async`.
- Parse task completed with `documentStatus=pending_review`, `chunkCount=1`, `parser=plain-text`, `assetAnalysisStatus=skipped`.
- Pending review item appeared in `/api/review/items?status=pending_review`.
- After approving the chunk, `/api/search` returned the document chunk with `reviewStatus=approved` and a traceable `chunkId`.

## Delivery Notes

- The default Docker path is now stable on LoongArch/Kylin without forcing Chroma installation.
- Chroma can still be attempted with `--build-arg INSTALL_CHROMA=true`, but it is not part of the target-environment main route until installation succeeds on LoongArch/Kylin.
- MinerU interface and fallback path are integrated, but real MinerU is not installed in the LoongArch container image in this verification run.
- Mock OCR is used in the verified container profile. OCR and multimodal provider failures degrade to reviewable pending chunks rather than blocking upload.
