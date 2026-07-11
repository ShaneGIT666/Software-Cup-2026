# Target Environment Strict Audit Plan

## Goal

Make LoongArch + Kylin the hard delivery boundary. Any feature, dependency, or claim that cannot run in the target competition environment must be downgraded to optional research/fallback, removed from the main route, or replaced with a target-compatible implementation.

## Steps

1. Read official problem and requirement documents for non-negotiable constraints.
2. Inventory runtime dependencies across backend, frontend, Docker, OCR, MinerU, vector search, and model providers.
3. Compare each dependency against evidence from the LoongArch/Kylin VM.
4. Mark each capability as keep, keep with fallback, optional only, or replace/drop.
5. Extract practical design patterns from mature open-source projects without importing unverified heavy runtimes.
6. Update code defaults and documentation so the main delivery route matches target-environment evidence.
7. Re-run local verification and record any blocked target-environment checks.

## Current Decision

The target delivery route is Docker on LoongArch/Kylin with FastAPI + Vue static assets, JSON business data store, pypdf text parsing fallback, real OpenAI-compatible Qwen LLM, approved-only retrieval, and the built-in SQLite vector store. JSON vector index remains a pure-file fallback. Chroma, MinerU, RapidOCR/PaddleOCR, local LLM runtimes, and system OCR are optional only until they are proven in the target environment.

## Final Submission Closure Goal

Complete the last pre-submission round without broad refactors. The required result is a more complete contest submission: cross-modal signal matching is visible and testable, RAG answer correction has a reviewable feedback loop, five formal submission documents exist, PPT/video preparation materials are aligned, engineering tests pass, and the final report clearly recommends whether to submit.

## Final Submission Steps

1. [complete] Audit starting git state and read the required product, architecture, backend, frontend, and test files.
2. [complete] Add low-risk cross-modal signal visibility to `/api/multimodal/diagnosis`.
3. [complete] Add minimal RAG feedback / answer correction review flow.
4. [complete] Add frontend entry points for cross-modal signals and RAG feedback.
5. [complete] Add or update tests for cross-modal signals and RAG feedback.
6. [complete] Create five formal `docs/submission/` documents and the package checklist.
7. [complete] Update official compliance matrix, PPT/video assets, and final engineering report.
8. [complete] Run backend tests, frontend build, readiness, JSON maintenance, API smoke, and sensitive file checks.
9. [in_progress] Commit and push if all required checks pass.

## Final Submission Starting State

- Branch: `main...origin/main`
- Latest commit at start: `952e5a9 finalize delivery verification docs`
- Worktree at start: clean
- Initial catchup note: `python` was not on PATH; reran planning catchup with `backend/.venv/Scripts/python.exe` successfully.

## Full Trust Hardening Goal

Execute the 2026-07-11 full-trust hardening plan in `E:/Download/Downloads/Software-Cup-2026_GPT-5.5-High_Agent全量整改执行计划.md`. Preserve existing user changes, avoid broad refactors, keep the FastAPI + Vue + lightweight retrieval architecture, and make claims match verified LoongArch/Kylin/offline behavior.

## Full Trust Hardening Steps

1. [complete] T00 baseline protection: record branch, HEAD, dirty worktree, runtime versions, targeted backend tests, and frontend build.
2. [complete] T01-T02 retrieval hardening: make RRF fusion the primary sort key and retrieve an expanded candidate pool before rerank/final topK clipping.
3. [complete] T03-T04 knowledge review governance: version revised chunks and make approved-only filtering fail closed.
4. [complete] T05-T06 RAG answer safety: preserve safety-processed structured output as the only final answer and refuse concrete steps without approved evidence.
5. [in_progress] T07-T08 business metadata and role protection.
6. [pending] T09-T15 metadata, Chinese query expansion, corrective retrieval, structured validation, multimodal consistency, and safety rules.
7. [pending] T16-T17 JSON transaction protection and index/task recovery.
8. [pending] T18-T19 evaluation dataset, runner, ablation modes, and hard gates.
9. [pending] T20-T21 frontend contract, deployment config, README, and submission docs.
10. [pending] T22 final full verification and execution report.

## Full Trust Hardening Starting State

- Branch before switch: `main`
- Hardening branch: `codex/full-trust-hardening-20260711`
- HEAD: `09f9b3a0cd485e12b51a289996f4e3a44e0ae542`
- Pre-existing user changes: `data/examples/repair-cases.json`, `tmp/`
- Baseline targeted backend tests: `21 passed in 2.70s`
- Baseline frontend build: passed in `5.88s`
