# Final Submission Gate

## Evidence Baseline

- Current Git SHA at gate documentation: `a8bd97756801f64427d70377588ae89c9192018d`
- Local Renderer: `pymupdf`, `ready=true`, `smokeRenderOk=true`
- MinerU actual CLI version: `mineru, version 3.2.3`
- Multimodal provider probe: OpenAI-compatible `qwen3.6-flash`, `probeOk=true`

## Executed Runtime Evidence

| Gate | Executed result |
| --- | --- |
| Three-page real multimodal | `THREE_PAGE_REAL_MULTIMODAL_GO`; 3/3 rendered and semantically verified, coverage 1.0, fallback 0 |
| 41-page smart | `SMART_MULTIMODAL_MANUAL_GO`; 41/41 real multimodal, 969.515 seconds |
| 41-page full | `FULL_VISUAL_MANUAL_GO;MULTIMODAL_RETRIEVAL_GO`; 41/41 pages and 82/82 MinerU assets real, 2460.14 seconds |
| 20-page machine quality audit | `MACHINE_VISUAL_QUALITY_GO_SAME_MODEL`; 20 completed, 18 passed, average 9.6, lowest 6 |
| Machine hallucination checks | 0 critical hallucination pages; 0 unsupported numeric-claim pages |
| Human review | `HUMAN_VISUAL_REVIEW_PENDING`; 0 PASS, 0 FAIL, no result was fabricated |

The machine quality conclusion used the same configured provider and model for primary analysis and judging. It is not an independent-model or human acceptance result.

## Compatibility And Target

### Pydantic 1

- A clean temporary environment installed `pydantic==1.10.26` successfully.
- The first mandated `py -3` invocation selected Python 3.9. Project PEP 604 annotations cannot be evaluated by that Python version, so collection stopped before focused tests ran.
- Rebuilding the isolated environment on the project's Python 3.12 runtime requires a fresh sandbox-external dependency installation approval. That approval is not yet available.
- Current result: `LOCAL_PYDANTIC1_COMPAT_NO_GO`.

### LoongArch

- The target identity was revalidated with strict SSH host-key checking. The accepted target is LoongArch64/Kylin V11 on Loongson-3A5000 at code SHA `d47ea9bc1e03148df7c55517a5b47367709e57f8`.
- User-local official Kylin `pdftoppm 23.12.0` passed operational readiness and smoke rendering.
- The real provider passed its probe, and the three-page official-manual run passed with 3/3 real multimodal pages, zero fallbacks, approved-only retrieval, and controlled preview.
- Strict target venv verification passed with 327 backend tests and a successful frontend production build.
- Docker is separately `OPTIONAL_UNVERIFIED` because the daemon is inactive and its socket is absent.
- Current result: `LOONGARCH_MULTIMODAL_GO` and `TARGET_CORE_GO`.

## Engineering Regression

| Check | Result |
| --- | --- |
| Focused tests | `163 passed` in 178.25 seconds |
| Full backend tests | `317 passed` in 985.23 seconds |
| Frontend build | passed; Vite build 8.32 seconds |
| `git diff --check` | passed |
| Sensitive scan | 11 unchanged baseline placeholder/config matches; 0 changed-file matches |
| Protected user files | pre-existing `repair-cases.json` modification and `tmp/` remain unstaged and uncommitted |
| Remote CI | `REMOTE_CI_UNAVAILABLE` |

## Unresolved Blockers

1. Pydantic 1.10.26 focused tests have not passed on the project Python 3.12 runtime.
2. At least 10 of the 20 human-review pages must be marked PASS, with no critical hallucination or fabricated numeric value.
3. Docker acceptance may be added after an administrator enables the target daemon; it is not claimed by the current venv acceptance.

## Conclusion

- Visual metrics: `VISUAL_METRICS_GO`
- MinerU version: `MINERU_VERSION_GO`
- Local Pydantic 1 compatibility: `LOCAL_PYDANTIC1_COMPAT_NO_GO`
- Machine visual quality: `MACHINE_VISUAL_QUALITY_GO_SAME_MODEL`
- Human visual review: `HUMAN_VISUAL_REVIEW_PENDING`
- LoongArch: `LOONGARCH_MULTIMODAL_GO` / `TARGET_CORE_GO`
- Local engineering: `LOCAL_FINAL_ENGINEERING_NO_GO`
- Submission: `FINAL_SUBMISSION_NO_GO`

The branch is ready for review as a truthful freeze candidate, but it must not be represented as `FINAL_SUBMISSION_GO` while these blockers remain.
