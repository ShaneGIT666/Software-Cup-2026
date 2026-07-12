# Current Capability Matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Local backend regression | VERIFIED_LOCAL | Current pytest baseline |
| Local frontend production build | VERIFIED_LOCAL | Current Vite build baseline |
| Approved-only retrieval and RRF ordering | VERIFIED_LOCAL | Retrieval regression tests |
| Secure role-token delivery configuration | VERIFIED_LOCAL | Init-config and auth contract tests |
| Mock and fallback route | VERIFIED_LOCAL | Local API tests; not a real model claim |
| Strict acceptance harness | VERIFIED_LOCAL | Fail-closed contract tests, Bash syntax, and pending-only local preflight |
| Official manual API acceptance | OPTIONAL_UNVERIFIED | 41-page PDF is present on target; strict run stopped before API smoke |
| LoongArch/Kylin acceptance for current SHA | OPTIONAL_UNVERIFIED | LoongArch64/Kylin V11 detected; first strict summary is `NO-GO` |
| Real LLM | OPTIONAL_UNVERIFIED | Actual RAG response and non-fallback provider status required |
| Real multimodal | OPTIONAL_UNVERIFIED | Actual image diagnosis and non-fallback analysis required |
| Docker target route | OPTIONAL_UNVERIFIED | Docker 24.0.9 is present; strict container route has not passed |
