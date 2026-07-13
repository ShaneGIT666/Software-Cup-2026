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
