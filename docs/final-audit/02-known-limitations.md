# Known Limitations

- This workstation is not proof of LoongArch or Kylin compatibility.
- Real LLM and multimodal verification require target credentials and a real fault image; mock/fallback results are not real-provider evidence.
- The final acceptance harness returns `NO-GO` for missing strict prerequisites and `TARGET_VERIFICATION_PENDING` for preflight-only runs.
- Optional target dependencies remain optional until proven on the target machine.
