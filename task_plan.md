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
