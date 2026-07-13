#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ROOT="/tmp/software-cup-multimodal-verify-$(date -u +%Y%m%dT%H%M%SZ)-$$"
PYTHON_BIN=""
SMOKE_OUTPUT="$RUN_ROOT/three-page-smoke.json"

cleanup() {
  local status=$?
  trap - EXIT
  case "$RUN_ROOT" in
    /tmp/software-cup-multimodal-verify-*) rm -rf -- "$RUN_ROOT" ;;
    *) echo "refusing unsafe cleanup path" >&2; status=1 ;;
  esac
  if [[ "$status" -ne 0 ]]; then
    echo "LOONGARCH_MULTIMODAL_NO_GO"
  fi
  exit "$status"
}
trap cleanup EXIT
mkdir -p "$RUN_ROOT"

if [[ -z "${OFFICIAL_MANUAL_PATH:-}" && -f .env ]]; then
  while IFS='=' read -r key value; do
    if [[ "$key" == "OFFICIAL_MANUAL_PATH" ]]; then
      OFFICIAL_MANUAL_PATH="${value%$'\r'}"
    fi
  done < .env
fi
if [[ -z "${OFFICIAL_MANUAL_PATH:-}" && -f /home/vmuser/official-motorcycle-manual.pdf ]]; then
  OFFICIAL_MANUAL_PATH="/home/vmuser/official-motorcycle-manual.pdf"
fi
[[ -n "${OFFICIAL_MANUAL_PATH:-}" && -s "$OFFICIAL_MANUAL_PATH" ]] || { echo "OFFICIAL_MANUAL_PATH_NO_GO"; exit 1; }
export OFFICIAL_MANUAL_PATH

arch="$(uname -m)"
echo "architecture=$arch"
[[ "$arch" == *loongarch* ]] || { echo "TARGET_ARCH_NO_GO"; exit 1; }

for candidate in backend/.venv/bin/python .venv/bin/python venv/bin/python python3; do
  if [[ "$candidate" == "python3" ]]; then
    command -v python3 >/dev/null 2>&1 || continue
  elif [[ ! -x "$candidate" ]]; then
    continue
  fi
  if "$candidate" -c 'import backend.app.main, pydantic, fastapi, pypdf' >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
[[ -n "$PYTHON_BIN" ]] || { echo "TARGET_PYTHON_NO_GO"; exit 1; }

"$PYTHON_BIN" --version
"$PYTHON_BIN" -c 'import fastapi,pydantic; print("pydantic=" + pydantic.__version__); print("fastapi=" + fastapi.__version__)'
"$PYTHON_BIN" -c 'import pydantic; print("TARGET_PYDANTIC1_DETECTED" if pydantic.__version__.startswith("1.") else "TARGET_PYDANTIC_VERSION_RECORDED")'

command -v pdftoppm >/dev/null 2>&1 || { echo "LOONGARCH_RENDERER_REQUIRES_ADMIN"; exit 1; }
pdftoppm -v
"$PYTHON_BIN" -c 'import json; from backend.app.pdf_renderer import renderer_operational_readiness; d=renderer_operational_readiness(); print(json.dumps(d,ensure_ascii=False)); assert d.get("ready") is True and d.get("renderer") == "pdftoppm" and d.get("smokeRenderOk") is True'

"$PYTHON_BIN" -c 'import json; from backend.app.multimodal_adapter import multimodal_readiness,multimodal_operational_probe; r=multimodal_readiness(); p=multimodal_operational_probe(); safe={"provider":r.get("provider"),"model":r.get("model"),"ready":r.get("ready"),"probeOk":p.get("probeOk")}; print(json.dumps(safe,ensure_ascii=False)); assert r.get("ready") is True and r.get("provider") != "mock" and p.get("probeOk") is True'

export TMPDIR="$RUN_ROOT" TMP="$RUN_ROOT" TEMP="$RUN_ROOT"
export MANUAL_SMOKE_TMP_ROOT="$RUN_ROOT" MANUAL_SMOKE_OUTPUT="$SMOKE_OUTPUT"
"$PYTHON_BIN" scripts/manual-multimodal-smoke.py
"$PYTHON_BIN" - "$SMOKE_OUTPUT" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rendered = int(data.get("visualPagesRendered") or 0)
assert data.get("result") == "THREE_PAGE_REAL_MULTIMODAL_GO", data
assert int(data.get("pageCount") or 0) == 3 and rendered > 0, data
assert int(data.get("realMultimodalPages") or 0) == rendered, data
assert int(data.get("unverifiedVisualPages") or 0) == 0, data
assert int(data.get("fallbackVisualPages") or 0) == 0 and not data.get("visualFailedPages"), data
assert data.get("pendingReviewAll") is True and data.get("semanticVerifiedAll") is True, data
assert data.get("unapprovedNotRetrievable") is True and data.get("approvedRetrievable") is True, data
assert data.get("controlledPreviewPassed") is True, data
print(json.dumps({
    "pageCount": data["pageCount"], "visualPagesRendered": rendered,
    "realMultimodalPages": data["realMultimodalPages"], "fallbackVisualPages": data["fallbackVisualPages"],
    "pendingReviewAll": data["pendingReviewAll"], "approvedOnly": True,
    "controlledPreviewPassed": data["controlledPreviewPassed"], "result": data["result"],
}, ensure_ascii=False))
PY

export TARGET_VERIFY_EVIDENCE_ROOT="$RUN_ROOT/final-evidence"
export PYTEST_ADDOPTS="-p no:cacheprovider"
export REQUIRE_REAL_LLM="true" REQUIRE_REAL_MULTIMODAL="false"
bash scripts/loongarch-final-verify.sh --venv --strict-target
echo "loongarch-final-verify=passed"
echo "LOONGARCH_MULTIMODAL_GO"
