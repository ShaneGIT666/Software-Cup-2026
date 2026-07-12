# Known Limitations

- This workstation is not proof of LoongArch or Kylin compatibility.
- Real LLM and multimodal verification require target credentials and a real fault image; mock/fallback results are not real-provider evidence.
- The final acceptance harness returns `TARGET_VERIFICATION_PENDING` for every non-strict run. A strict run returns `GO` only after all architecture, OS, backend, frontend, auth, API, official-manual, and requested real-provider gates pass; otherwise it records `NO-GO` and exits non-zero.
- Raw target evidence is ignored by Git. Only manually reviewed, secret-free summaries may be copied into tracked audit documents.
- The official manual test fixture may be skipped outside acceptance when no PDF is available, but strict target acceptance requires a non-empty `.pdf` and a complete API verification chain.
- First target run on LoongArch64/Kylin V11 produced `NO-GO`: no real provider credentials or real fault image were available, so real LLM and multimodal gates remain false.
- `backend/requirements.txt` currently pins `pydantic<2`, while runtime code imports Pydantic 2 `field_validator`; a clean target install therefore fails during pytest collection. A temporary Pydantic 2 source install also stalled because no LoongArch `pydantic-core` wheel was available.
- Baseline `scripts/init-config.sh` is stored with CRLF and cannot run directly under target Bash. The first-round setup used an untracked, immediately removed LF copy; this remains a delivery limitation outside the current allowed file scope.
- Target Node.js is 20.18.2, below Vite's declared 20.19 minimum. The production build completed successfully, but the engine warning remains.
- Optional target dependencies remain optional until proven on the target machine.
