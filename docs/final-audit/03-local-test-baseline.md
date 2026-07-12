# Local Test Baseline

The Stage 1 Linux delivery repair was validated locally with `3 passed in 1.48s` for the shell behavior suite, `223 passed in 49.20s` for the full backend suite, a frontend production build in `5.17s`, and shell syntax checks.

The finalization branch baseline was validated locally with `119 passed in 13.53s` for delivery/init/API contracts, `225 passed in 49.82s` for the full backend suite, a frontend production build in `5.19s`, and successful `--preflight` execution. The preflight machine was Windows Git Bash on x86_64, so it is not LoongArch/Kylin evidence.

The baseline must be refreshed after every finalization-branch commit; do not reuse historical test counts as current evidence.
