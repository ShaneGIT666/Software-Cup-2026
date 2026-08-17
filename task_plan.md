# Target Environment Strict Audit Plan

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

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
