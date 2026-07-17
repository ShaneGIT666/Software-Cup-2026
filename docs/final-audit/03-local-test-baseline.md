# Local Test Baseline

The Stage 1 Linux delivery repair was validated locally with `3 passed in 1.48s` for the shell behavior suite, `223 passed in 49.20s` for the full backend suite, a frontend production build in `5.17s`, and shell syntax checks.

The finalization branch baseline was validated locally with `119 passed in 13.53s` for delivery/init/API contracts, `225 passed in 49.82s` for the full backend suite, a frontend production build in `5.19s`, and successful `--preflight` execution. The preflight machine was Windows Git Bash on x86_64, so it is not LoongArch/Kylin evidence.

The baseline must be refreshed after every finalization-branch commit; do not reuse historical test counts as current evidence.

The final Bailian/Pydantic stage baseline is `136 passed in 173.30s` for the required targeted suite, `245 passed in 213.30s` for the full backend suite, and a frontend production build in `5.93s`. Bash syntax and `git diff --check` passed. The local temporary Pydantic 1 installation was blocked by the workstation network sandbox, while the target clean environment installed and verified Pydantic 1.10.26 successfully.

## Final acceptance refresh (2026-07-17)

- Full backend: `327 passed in 230.89s`.
- Focused final gates: `23 passed in 6.09s`.
- Disposable Python 3.12.13 + Pydantic 1.10.26 compatibility: `4 passed in 0.07s`; temporary venv removed after validation.
- Frontend production build: passed in `5.82s`.
- Production readiness: seven checks passed in `4475.17ms`.
- JSON store maintenance: seven files valid, zero issues, zero repairs.
- Final benchmark: passed; official smoke subset `5 passed in 4.34s`.
- Bash syntax, `git diff --check`, and acceptance-change secret scan passed.
