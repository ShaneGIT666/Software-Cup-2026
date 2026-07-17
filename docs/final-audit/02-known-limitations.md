# Known Limitations

- This workstation is not proof of LoongArch or Kylin compatibility.
- Real text LLM and official-manual multimodal verification require target credentials; both passed on the target. A separate field fault-photo claim still requires an actual fault image, and mock/fallback results are not used as real-provider evidence.
- The final acceptance harness returns `TARGET_VERIFICATION_PENDING` for every non-strict run. A strict run returns `GO` only after all architecture, OS, backend, frontend, auth, API, official-manual, and requested real-provider gates pass; otherwise it records `NO-GO` and exits non-zero.
- Raw target evidence is ignored by Git. Only manually reviewed, secret-free summaries may be copied into tracked audit documents.
- The official manual test fixture may be skipped outside acceptance when no PDF is available, but strict target acceptance requires a non-empty `.pdf` and a complete API verification chain.
- Pydantic compatibility is closed by pinning `pydantic>=1.10.13,<2` and using Pydantic 1 validators; the fresh target suite passed 327 tests with Pydantic 1.10.26, and a disposable local Python 3.12/Pydantic 1 environment passed all four focused compatibility tests.
- Real qwen3.6-flash text generation is verified, but the safety pipeline continues to select the structured evidence answer (`llmAnswerUsed=false`, `finalAnswerSource=template`) after the one permitted fixed-heading prompt adjustment. This is not reported as direct model-answer adoption.
- Real fault-image multimodal verification was intentionally skipped. Adapter unit tests are not real image evidence, so `realMultimodalVerified=false` and `finalRealProviderVerified=false` remain required.
- Docker 24.0.9 CLI is installed on target, but `/var/run/docker.sock` was unavailable; strict Docker acceptance therefore produced `NO-GO` before build and pytest.
- `scripts/init-config.sh` and both LoongArch acceptance scripts are stored and checked out with LF line endings, so the earlier CRLF delivery limitation is closed.
- Target Node.js is 20.18.2, below Vite's declared 20.19 minimum. The production build completed successfully, but the engine warning remains.
- Optional target dependencies remain optional until proven on the target machine.
