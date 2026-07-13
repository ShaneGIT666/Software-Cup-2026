# Known Limitations

- This workstation is not proof of LoongArch or Kylin compatibility.
- Real LLM and multimodal verification require target credentials and a real fault image; mock/fallback results are not real-provider evidence.
- The final acceptance harness returns `TARGET_VERIFICATION_PENDING` for every non-strict run. A strict run returns `GO` only after all architecture, OS, backend, frontend, auth, API, official-manual, and requested real-provider gates pass; otherwise it records `NO-GO` and exits non-zero.
- Raw target evidence is ignored by Git. Only manually reviewed, secret-free summaries may be copied into tracked audit documents.
- The official manual test fixture may be skipped outside acceptance when no PDF is available, but strict target acceptance requires a non-empty `.pdf` and a complete API verification chain.
- Pydantic compatibility is closed by pinning `pydantic>=1.10.13,<2` and using Pydantic 1 validators; target app import and 245 target tests passed with Pydantic 1.10.26.
- Real qwen3.6-flash text generation is verified, but the safety pipeline continues to select the structured evidence answer (`llmAnswerUsed=false`, `finalAnswerSource=template`) after the one permitted fixed-heading prompt adjustment. This is not reported as direct model-answer adoption.
- Real fault-image multimodal verification was intentionally skipped. Adapter unit tests are not real image evidence, so `realMultimodalVerified=false` and `finalRealProviderVerified=false` remain required.
- Docker 24.0.9 CLI is installed on target, but `/var/run/docker.sock` was unavailable; strict Docker acceptance therefore produced `NO-GO` before build and pytest.
- Baseline `scripts/init-config.sh` is stored with CRLF and cannot run directly under target Bash. The first-round setup used an untracked, immediately removed LF copy; this remains a delivery limitation outside the current allowed file scope.
- Target Node.js is 20.18.2, below Vite's declared 20.19 minimum. The production build completed successfully, but the engine warning remains.
- Optional target dependencies remain optional until proven on the target machine.
