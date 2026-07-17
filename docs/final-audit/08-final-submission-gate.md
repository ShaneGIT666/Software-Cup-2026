# Final Submission Gate

## Evidence Baseline

- Accepted application Git SHA: `d47ea9bc1e03148df7c55517a5b47367709e57f8`
- Final acceptance refresh: `2026-07-17`
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
| Human review | `HUMAN_VISUAL_REVIEW_GO`; 17 TRUE/PASS submitted, 1 FALSE/FAIL, 2 blank; page 6 excluded conservatively, leaving 16 valid PASS |

The machine quality conclusion used the same configured provider and model for primary analysis and judging. It is not an independent-model or human acceptance result.

## Compatibility And Target

### Pydantic 1

- A disposable Python 3.12.13 environment installed pinned `pydantic==1.10.26` and `pytest==8.4.2` successfully.
- `tests/test_pydantic_compat.py` passed 4/4 tests in 0.07 seconds, and the disposable environment was removed after validation.
- The target full suite independently passed under Pydantic 1.10.26.
- Current result: `LOCAL_PYDANTIC1_COMPAT_GO`.

### LoongArch

- The target identity was revalidated with strict SSH host-key checking. The accepted target is LoongArch64/Kylin V11 on Loongson-3A5000 at code SHA `d47ea9bc1e03148df7c55517a5b47367709e57f8`.
- User-local official Kylin `pdftoppm 23.12.0` passed operational readiness and smoke rendering.
- The real provider passed its probe, and the three-page official-manual run passed with 3/3 real multimodal pages, zero fallbacks, approved-only retrieval, and controlled preview.
- A fresh 2026-07-17 strict target run passed 327 backend tests in 344.90 seconds and rebuilt the frontend in 20.27 seconds.
- Docker is separately `OPTIONAL_UNVERIFIED` because the daemon is inactive and its socket is absent.
- Current result: `LOONGARCH_MULTIMODAL_GO` and `TARGET_CORE_GO`.

## Engineering Regression

| Check | Result |
| --- | --- |
| Focused final gates | `23 passed` in 6.09 seconds; isolated Pydantic 1 `4 passed` in 0.07 seconds |
| Full backend tests | `327 passed` in 230.89 seconds |
| Frontend build | passed; Vite build 5.82 seconds |
| Production readiness | seven checks passed in 4475.17 ms |
| JSON store maintenance | seven files valid; zero issues and zero repairs |
| Final benchmark | passed; official smoke `5 passed` in 4.34 seconds |
| `git diff --check` | passed |
| Sensitive scan | zero acceptance-change secret matches; zero tracked private env files; generated-token code false positive reviewed |
| Protected user files | pre-existing `repair-cases.json` modification and `tmp/` remain unstaged and uncommitted |
| Remote CI | `REMOTE_CI_UNAVAILABLE` |

## Remaining Optional Boundaries

Docker acceptance may be added after an administrator enables the target daemon. Docker is optional under the accepted venv + FastAPI static-hosting route and is not claimed by current evidence. A separate field fault-photo result also remains optional because no such image was supplied; neither item is a final-submission hard gate.

## Conclusion

- Visual metrics: `VISUAL_METRICS_GO`
- MinerU version: `MINERU_VERSION_GO`
- Local Pydantic 1 compatibility: `LOCAL_PYDANTIC1_COMPAT_GO`
- Machine visual quality: `MACHINE_VISUAL_QUALITY_GO_SAME_MODEL`
- Human visual review: `HUMAN_VISUAL_REVIEW_GO`
- LoongArch: `LOONGARCH_MULTIMODAL_GO` / `TARGET_CORE_GO`
- Local engineering: `LOCAL_FINAL_ENGINEERING_GO`
- Submission: `FINAL_SUBMISSION_GO`

All required engineering, LoongArch target, machine visual, and human visual gates are GO. The branch is accepted as `FINAL_SUBMISSION_GO`; optional Docker and separate field fault-photo claims remain explicitly outside this conclusion.
