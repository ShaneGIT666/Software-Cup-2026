# Full Trust Hardening Baseline

Date: 2026-07-11

## Git

- Original branch before hardening branch: `main`
- Hardening branch: `codex/full-trust-hardening-20260711`
- Original HEAD: `09f9b3a0cd485e12b51a289996f4e3a44e0ae542`
- `git diff --check`: passed with no output
- Worktree at start: dirty

## Preserved User Changes

- Modified: `data/examples/repair-cases.json`
- Untracked: `tmp/`

These entries existed before hardening work began and must not be reverted or overwritten.

## Runtime

- Backend Python: `Python 3.12.13` from `backend/.venv/Scripts/python.exe`
- System `python`: not available on PATH
- Node: `v24.15.0`
- npm: `11.12.1`
- Backend virtualenv: `backend/.venv`

## Baseline Checks

- Targeted backend baseline:
  - Command: `backend/.venv/Scripts/python.exe -m pytest tests/test_retrieval_pipeline.py tests/test_evidence_pack.py tests/test_chunk_revision_audit.py tests/test_multimodal_diagnosis.py tests/test_corrective_rag.py tests/test_safety_rules.py -q`
  - Result: `21 passed in 2.70s`
- Frontend production build:
  - Command: `npm.cmd --prefix frontend run build`
  - Result: passed, built in `5.88s`
  - Notes: Vite reported existing Rollup pure-annotation warnings and a chunk size warning.

## Branch Safety

The dedicated hardening branch was created after recording the starting state. Existing local user changes remained present on the new branch.
