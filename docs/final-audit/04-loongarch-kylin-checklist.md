# LoongArch Kylin Checklist

1. Fetch `codex/contest-finalization-20260712` and fast-forward only.
2. Install the backend venv dependencies and build `frontend/dist`; if npm is unavailable, record the current-SHA prebuilt artifact used.
3. Run `bash scripts/init-config.sh --mode llm --force`; enter the API key interactively and keep `.env` untracked.
4. Set `MULTIMODAL_PROVIDER=openai`, `OFFICIAL_MANUAL_PATH`, `REAL_IMAGE_PATH`, `REQUIRE_REAL_LLM=true`, and `REQUIRE_REAL_MULTIMODAL=true` in the uncommitted target environment.
5. Confirm the official manual is a non-empty PDF and the real image is a non-empty jpg/jpeg/png/webp without printing secrets.
6. Run `bash scripts/loongarch-final-verify.sh --venv --strict-target` and require every summary gate, including `officialManualVerified`, to be true.
7. Run `bash scripts/loongarch-final-verify.sh --docker --strict-target` only when Docker exists; otherwise record Docker as `OPTIONAL_UNVERIFIED`.
8. Inspect the ignored evidence directory, redact any provider responses before reporting, and require `summary.json` to report `GO` before marking Stage 2 complete.
