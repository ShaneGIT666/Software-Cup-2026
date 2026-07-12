# Current Capability Matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Local backend regression | VERIFIED_LOCAL | Current pytest baseline |
| Local frontend production build | VERIFIED_LOCAL | Current Vite build baseline |
| Approved-only retrieval and RRF ordering | VERIFIED_LOCAL | Retrieval regression tests |
| Secure role-token delivery configuration | VERIFIED_LOCAL | Init-config and auth contract tests |
| Mock and fallback route | VERIFIED_LOCAL | Local API tests; not a real model claim |
| Strict acceptance harness | VERIFIED_LOCAL | Fail-closed contract tests, Bash syntax, and pending-only local preflight |
| Official manual API acceptance | OPTIONAL_UNVERIFIED | Strict target run must upload, approve, retrieve, cite, and download the configured PDF |
| LoongArch/Kylin acceptance for current SHA | OPTIONAL_UNVERIFIED | Target machine evidence required |
| Real LLM | OPTIONAL_UNVERIFIED | Actual RAG response and non-fallback provider status required |
| Real multimodal | OPTIONAL_UNVERIFIED | Actual image diagnosis and non-fallback analysis required |
| Docker target route | OPTIONAL_UNVERIFIED | Target Docker availability and container test evidence required |
