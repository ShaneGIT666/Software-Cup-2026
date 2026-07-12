# LoongArch Kylin Checklist

1. Fetch `codex/contest-finalization-20260712` and fast-forward only.
2. Run `bash scripts/init-config.sh --mode llm --force`; enter the API key interactively.
3. Set `MULTIMODAL_PROVIDER=openai`, `OFFICIAL_MANUAL_PATH`, `REAL_IMAGE_PATH`, `REQUIRE_REAL_LLM=true`, and `REQUIRE_REAL_MULTIMODAL=true` in the uncommitted local environment.
4. Run `bash scripts/loongarch-final-verify.sh --venv --strict-target`.
5. Optionally run `bash scripts/loongarch-final-verify.sh --docker --strict-target`.
6. Inspect the new evidence directory and require `summary.json` to report `GO` before marking Stage 2 complete.
