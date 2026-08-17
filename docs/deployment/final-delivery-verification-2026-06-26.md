# Final Delivery Verification, 2026-06-26

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

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
