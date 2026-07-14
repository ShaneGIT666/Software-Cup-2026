# LoongArch Kylin Checklist

1. Fetch `codex/contest-finalization-20260712` and fast-forward only.
2. Install the backend venv dependencies and build `frontend/dist`; if npm is unavailable, record the current-SHA prebuilt artifact used.
3. Run `bash scripts/init-config.sh --mode llm --force`; enter the API key interactively and keep `.env` untracked.
4. Set `MULTIMODAL_PROVIDER=openai`, `OFFICIAL_MANUAL_PATH`, `REAL_IMAGE_PATH`, `REQUIRE_REAL_LLM=true`, and `REQUIRE_REAL_MULTIMODAL=true` in the uncommitted target environment.
5. Confirm the official manual is a non-empty PDF and the real image is a non-empty jpg/jpeg/png/webp without printing secrets.
6. Run `bash scripts/loongarch-final-verify.sh --venv --strict-target` and require every summary gate, including `officialManualVerified`, to be true.
7. Run `bash scripts/loongarch-final-verify.sh --docker --strict-target` only when Docker exists; otherwise record Docker as `OPTIONAL_UNVERIFIED`.
8. Inspect the ignored evidence directory, redact any provider responses before reporting, and require `summary.json` to report `GO` before marking Stage 2 complete.

## First-round result (2026-07-12)

- Target: `loongarch64`, Kylin Linux Advanced Server V11, Loongson-3A5000.
- Current harness SHA: `dc8e0d4b02649d744f1b64e2073f0a63a249c769`.
- Frontend: built successfully on target; Node 20.18.2 emitted a Vite engine warning.
- Official fixture: 41-page, non-empty PDF transferred to `/home/vmuser/official-motorcycle-manual.pdf`.
- Strict venv summary: `NO-GO`; missing real fault image stopped the run before backend/auth/API/manual/provider gates.
- Backend preparation: clean requirements install selected Pydantic 1.10.26, but code requires Pydantic 2 and pytest collection failed with 12 import errors.
- Real LLM and multimodal: not verified; no real API key or real device fault image was available.
- Docker: installed, but strict Docker acceptance was not run because the same dependency and provider prerequisites remain unresolved.

## Bailian core result (2026-07-13)

- Target: `loongarch64`, Kylin Linux Advanced Server V11, Loongson-3A5000.
- Pydantic: clean install selected 1.10.26; app import succeeded; strict target backend suite passed 245 tests.
- Frontend: production build passed in 18.11s; Node 20.18.2 engine warning remains recorded.
- Official manual: 42 chunks approved, 10 search hits, 10 citations, and controlled file download passed.
- Real text provider: `openai`, model `qwen3.6-flash`, API style `chat_completions`, fallback false, raw answer present.
- Prompt retry: the one permitted fixed-heading adjustment removed `missing_required_headings`; the safety pipeline still selected the structured evidence answer.
- Strict venv: `TARGET_CORE_GO`, `coreTargetVerified=true`, `realLlmVerified=true`, `realMultimodalVerified=false`, `finalRealProviderVerified=false`.
- Strict Docker: `NO-GO` because the Docker daemon socket was unavailable; no container result is claimed.
- Stage 2 status: `TARGET_CORE_GO`. Final `GO` remains forbidden until a real repair image passes strict multimodal verification.

## Final revalidation result (2026-07-14)

- Accepted code SHA: `d47ea9bc1e03148df7c55517a5b47367709e57f8` on branch `codex/fix-auth-management-runtime-20260714`.
- Target identity was revalidated with strict SSH host-key checking; architecture is `loongarch64`, OS is Kylin Linux Advanced Server V11, and CPU is Loongson-3A5000.
- The official Kylin LoongArch `poppler-utils` package was unpacked into a reversible user-local directory. `pdftoppm 23.12.0` passed the project renderer version and smoke-render checks.
- Real multimodal provider probe passed with provider `openai`, model `qwen3.6-flash`, `ready=true`, and `probeOk=true`.
- Three official-manual pages passed real visual analysis: 3/3 rendered, 3/3 real multimodal, zero fallback pages, all pending review before approval, approved-only retrieval enforced, and controlled preview passed.
- Strict venv acceptance passed: backend `327 passed in 353.88s`, frontend production build passed in `20.53s`, and auth, API, official-manual, approved-only retrieval, controlled download, and real text LLM gates passed.
- Harness results: `THREE_PAGE_REAL_MULTIMODAL_GO`, `TARGET_CORE_GO`, and outer acceptance result `LOONGARCH_MULTIMODAL_GO`.
- Docker remains `OPTIONAL_UNVERIFIED`: Docker CLI 24.0.9 is installed, but the daemon is inactive and `/var/run/docker.sock` is absent. No Docker success is claimed.
- This acceptance proves real multimodal processing of rendered official-manual pages. It does not fabricate a separate real motorcycle-fault-photo result because no such image was supplied on the target.
