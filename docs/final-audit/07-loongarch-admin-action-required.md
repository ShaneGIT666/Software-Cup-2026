# LoongArch Target Revalidation

## Accepted Evidence (2026-07-14)

- Code: `d47ea9bc1e03148df7c55517a5b47367709e57f8`.
- Target: `loongarch64`, Kylin Linux Advanced Server V11, Loongson-3A5000.
- Runtime: Python 3.11.6, Pydantic 1.10.26, FastAPI 0.115.6, Node 20.18.2, npm 10.8.2.
- Renderer: user-local official Kylin LoongArch `pdftoppm 23.12.0`; operational readiness returned `ready=true`, `renderer=pdftoppm`, `versionProbeOk=true`, and `smokeRenderOk=true`.
- Provider: real OpenAI-compatible `qwen3.6-flash`; multimodal readiness and operational probe both passed without logging credentials.
- Three-page official-manual flow: 3/3 rendered and analyzed by the real multimodal provider, zero fallback pages, review-before-retrieval enforced, approved-only retrieval passed, and controlled preview passed.
- Strict target regression: backend `327 passed in 353.88s`; frontend production build passed in `20.53s`.
- Strict application gates: auth, API, official-manual upload/review/retrieval/citation/download, and real text LLM passed.
- Persistent target log: `/home/vmuser/loongarch-acceptance-d47ea9b.log`.

## Docker Boundary

Docker CLI 24.0.9 is present, but `docker info` cannot connect, `systemctl is-active docker` reports `inactive`, and `/var/run/docker.sock` is absent. Strict Docker acceptance therefore remains `OPTIONAL_UNVERIFIED`; no container success is claimed. An administrator may enable the daemon and rerun:

```bash
bash scripts/loongarch-final-verify.sh --docker --strict-target
```

The verified venv + FastAPI static-hosting route remains the accepted target main route.

## Result

- `THREE_PAGE_REAL_MULTIMODAL_GO`
- `TARGET_CORE_GO`
- `LOONGARCH_MULTIMODAL_GO`

The former SSH host-identity blocker is superseded by this strict-host-key revalidation. The result covers real multimodal analysis of rendered official-manual pages; no separate motorcycle-fault-photo claim is made.
