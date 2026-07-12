# Known Limitations

- This workstation is not proof of LoongArch or Kylin compatibility.
- Real LLM and multimodal verification require target credentials and a real fault image; mock/fallback results are not real-provider evidence.
- The final acceptance harness returns `TARGET_VERIFICATION_PENDING` for every non-strict run. A strict run returns `GO` only after all architecture, OS, backend, frontend, auth, API, official-manual, and requested real-provider gates pass; otherwise it records `NO-GO` and exits non-zero.
- Raw target evidence is ignored by Git. Only manually reviewed, secret-free summaries may be copied into tracked audit documents.
- The official manual test fixture may be skipped outside acceptance when no PDF is available, but strict target acceptance requires a non-empty `.pdf` and a complete API verification chain.
- Optional target dependencies remain optional until proven on the target machine.
