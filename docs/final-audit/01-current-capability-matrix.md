# Current Capability Matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Local backend regression | VERIFIED_LOCAL | Current pytest baseline |
| Local frontend production build | VERIFIED_LOCAL | Current Vite build baseline |
| Approved-only retrieval and RRF ordering | VERIFIED_LOCAL | Retrieval regression tests |
| Secure role-token delivery configuration | VERIFIED_LOCAL | Init-config and auth contract tests |
| Mock and fallback route | VERIFIED_LOCAL | Local API tests; not a real model claim |
| Strict acceptance harness | VERIFIED_LOCAL | Fail-closed contract tests, Bash syntax, and pending-only local preflight |
| Official manual workflow | VERIFIED_TARGET | 42 chunks approved, 10 search hits, 10 RAG citations, controlled download passed |
| LoongArch/Kylin core | VERIFIED_TARGET | LoongArch64/Kylin V11 strict venv summary reported `TARGET_CORE_GO` |
| Real text LLM qwen3.6-flash | VERIFIED_TARGET | OpenAI-compatible chat-completions, no fallback, raw answer and 10 citations |
| Bailian multimodal adapter | VERIFIED_LOCAL | chat-completions image payload, fallback, responses path, and PDF-limit tests |
| Real official-manual multimodal | VERIFIED_TARGET | Fresh 2026-07-17 run analyzed 3/3 rendered pages with the real provider, zero fallbacks, approved-only retrieval, and controlled preview |
| Real fault-image multimodal | OPTIONAL_UNVERIFIED | Intentionally skipped; no field fault image was supplied |
| Docker target route | OPTIONAL_UNVERIFIED | Docker CLI exists but daemon socket was unavailable |
