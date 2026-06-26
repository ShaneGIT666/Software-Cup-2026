#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Software Cup final LoongArch/Kylin verification =="
date -Is
uname -a || true
printf "arch: "
uname -m || true

echo
echo "== Runtime =="
python3 --version
if command -v node >/dev/null 2>&1; then node --version; else echo "node: not found"; fi
if command -v npm >/dev/null 2>&1; then npm --version; else echo "npm: not found"; fi
if command -v docker >/dev/null 2>&1; then docker --version; else echo "docker: not found"; fi

echo
echo "== Backend tests =="
if [ -x "backend/.venv/bin/python" ]; then
  backend/.venv/bin/python -m pytest tests/ -q
else
  python3 -m pytest tests/ -q
fi

echo
echo "== Frontend build =="
if [ -d "frontend/node_modules" ]; then
  (cd frontend && npm run build)
else
  echo "frontend/node_modules missing, skip build. Install dependencies in target environment before final packaging."
fi

echo
echo "== Static checks =="
git diff --check

echo
echo "== API smoke =="
if command -v curl >/dev/null 2>&1; then
  curl -fsS http://127.0.0.1:8000/api/health || echo "health endpoint not reachable, start backend before API smoke."
  echo
  curl -fsS http://127.0.0.1:8000/api/providers/status || echo "provider endpoint not reachable, start backend before API smoke."
  echo
else
  echo "curl: not found, skip API smoke."
fi

echo
echo "Verification script completed. Fill docs/testing/loongarch-final-verification-template.md with the observed result."
