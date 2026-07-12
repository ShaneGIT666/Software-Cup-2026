#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE=""
STRICT_TARGET="false"
IMAGE_NAME="software-cup-final-verify:latest"
CONTAINER_NAME="software-cup-final-verify"
DOCKER_PORT="${DOCKER_PORT:-18080}"
RUN_DIR=""
BACKEND_PID=""
TEMP_DOCKER_ENV=""
BACKEND_TESTS_PASSED="false"
FRONTEND_PASSED="false"
AUTH_SMOKE_PASSED="false"
API_SMOKE_PASSED="false"
OFFICIAL_MANUAL_VERIFIED="false"
REAL_LLM_VERIFIED="false"
REAL_MULTIMODAL_VERIFIED="false"
CORE_TARGET_VERIFIED="false"
FINAL_REAL_PROVIDER_VERIFIED="false"
OFFICIAL_DOCUMENT_ID=""
PYTHON_BIN=""

usage() {
  cat <<'EOF'
Usage: bash scripts/loongarch-final-verify.sh [--preflight|--venv|--docker] [--strict-target]

--preflight     Collect local target-readiness evidence without changing the environment.
--venv          Run venv-based acceptance with a temporary runtime directory.
--docker        Build and run the Docker acceptance route with filtered container environment.
--strict-target Require LoongArch, Kylin, and all configured acceptance gates.
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "required command missing: $1" >&2; return 1; }
}

select_python() {
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif [[ -x backend/.venv/Scripts/python.exe ]]; then
    PYTHON_BIN="backend/.venv/Scripts/python.exe"
  else
    echo "required Python 3 interpreter is missing" >&2
    return 1
  fi
}

short_sha() { git rev-parse --short HEAD 2>/dev/null || echo unknown; }
safe_slug() { date -u +%Y%m%dT%H%M%SZ; }

new_evidence_dir() {
  RUN_DIR="$ROOT_DIR/docs/final-audit/evidence/$(safe_slug)-$(short_sha)"
  mkdir -p "$RUN_DIR"
}

write_summary() {
  local result="$1"
  export AUDIT_BACKEND_TESTS="$BACKEND_TESTS_PASSED" AUDIT_FRONTEND="$FRONTEND_PASSED"
  export AUDIT_AUTH_SMOKE="$AUTH_SMOKE_PASSED" AUDIT_API_SMOKE="$API_SMOKE_PASSED"
  export AUDIT_OFFICIAL_MANUAL="$OFFICIAL_MANUAL_VERIFIED"
  export AUDIT_REAL_LLM="$REAL_LLM_VERIFIED" AUDIT_REAL_MM="$REAL_MULTIMODAL_VERIFIED"
  export AUDIT_CORE_TARGET="$CORE_TARGET_VERIFIED" AUDIT_FINAL_PROVIDER="$FINAL_REAL_PROVIDER_VERIFIED"
  "$PYTHON_BIN" - "$RUN_DIR/summary.json" "$result" <<'PY'
import json, os, sys
path, result = sys.argv[1:]
payload = {
    "gitSha": os.environ.get("AUDIT_GIT_SHA", ""),
    "architecture": os.environ.get("AUDIT_ARCH", ""),
    "os": os.environ.get("AUDIT_OS", ""),
    "mode": os.environ.get("AUDIT_MODE", ""),
    "strictTarget": os.environ.get("AUDIT_STRICT", "false") == "true",
    "backendTestsPassed": os.environ.get("AUDIT_BACKEND_TESTS", "false") == "true",
    "frontendPassed": os.environ.get("AUDIT_FRONTEND", "false") == "true",
    "authSmokePassed": os.environ.get("AUDIT_AUTH_SMOKE", "false") == "true",
    "apiSmokePassed": os.environ.get("AUDIT_API_SMOKE", "false") == "true",
    "officialManualVerified": os.environ.get("AUDIT_OFFICIAL_MANUAL", "false") == "true",
    "realLlmVerified": os.environ.get("AUDIT_REAL_LLM", "false") == "true",
    "realMultimodalVerified": os.environ.get("AUDIT_REAL_MM", "false") == "true",
    "coreTargetVerified": os.environ.get("AUDIT_CORE_TARGET", "false") == "true",
    "finalRealProviderVerified": os.environ.get("AUDIT_FINAL_PROVIDER", "false") == "true",
    "result": result,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
}

strict_gates_passed() {
  [[ "$BACKEND_TESTS_PASSED" == "true" && "$FRONTEND_PASSED" == "true" ]] || return 1
  [[ "$AUTH_SMOKE_PASSED" == "true" && "$API_SMOKE_PASSED" == "true" ]] || return 1
  [[ "$OFFICIAL_MANUAL_VERIFIED" == "true" ]] || return 1
  [[ "${REQUIRE_REAL_LLM:-false}" != "true" || "$REAL_LLM_VERIFIED" == "true" ]] || return 1
  [[ "${REQUIRE_REAL_MULTIMODAL:-false}" != "true" || "$REAL_MULTIMODAL_VERIFIED" == "true" ]] || return 1
}

cleanup() {
  local status=$? result="TARGET_VERIFICATION_PENDING"
  trap - EXIT
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if command -v docker >/dev/null 2>&1; then docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; fi
  [[ -z "$TEMP_DOCKER_ENV" ]] || rm -f "$TEMP_DOCKER_ENV"
  if [[ "$STRICT_TARGET" == "true" && "$MODE" != "--preflight" ]]; then
    if [[ "$status" -eq 0 ]] && strict_gates_passed; then
      CORE_TARGET_VERIFIED="true"
      if [[ "$REAL_LLM_VERIFIED" == "true" && "$REAL_MULTIMODAL_VERIFIED" == "true" ]]; then
        FINAL_REAL_PROVIDER_VERIFIED="true"
        result="GO"
      elif [[ "$REAL_LLM_VERIFIED" == "true" && "${REQUIRE_REAL_MULTIMODAL:-false}" != "true" ]]; then
        result="TARGET_CORE_GO"
      else
        result="NO-GO"
        status=1
      fi
    else
      result="NO-GO"
      status=1
    fi
  fi
  write_summary "$result"
  exit "$status"
}

trap cleanup EXIT

read_env_value() {
  local key="$1" file="${2:-$ROOT_DIR/.env}"
  [[ -f "$file" ]] || return 1
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

config_value() {
  local key="$1" current="${!key:-}"
  if [[ -n "$current" ]]; then printf '%s' "$current"; else read_env_value "$key" || true; fi
}

require_role_tokens() {
  OPERATOR_TOKEN="$(config_value AUTH_OPERATOR_TOKEN)"
  REVIEWER_TOKEN="$(config_value AUTH_REVIEWER_TOKEN)"
  ADMIN_TOKEN="$(config_value AUTH_ADMIN_TOKEN)"
  [[ -n "$OPERATOR_TOKEN" && -n "$REVIEWER_TOKEN" && -n "$ADMIN_TOKEN" ]]
}

preflight() {
  {
    date -Is
    echo "git_sha=$(git rev-parse HEAD)"
    git status --short
    uname -a
    uname -m
    cat /etc/os-release 2>/dev/null || true
    lscpu 2>/dev/null || true
    free -h 2>/dev/null || true
    df -h
    "$PYTHON_BIN" --version 2>/dev/null || echo "python3: not found"
    node --version 2>/dev/null || true
    npm --version 2>/dev/null || true
    docker --version 2>/dev/null || true
  } | tee "$RUN_DIR/preflight.log"
  cp "$RUN_DIR/preflight.log" "$RUN_DIR/environment.txt"
}

check_strict_target() {
  local arch os_release
  arch="$(uname -m)"
  os_release="$(cat /etc/os-release 2>/dev/null || true)"
  [[ "$arch" == "loongarch64" || "$arch" == "loongarch" ]] || { echo "strict target requires LoongArch" >&2; return 1; }
  grep -Eiq 'kylin|银河麒麟|银河' <<<"$os_release" || { echo "strict target requires Kylin" >&2; return 1; }
}

validate_official_manual() {
  [[ -n "${OFFICIAL_MANUAL_PATH:-}" ]] || { echo "strict target requires OFFICIAL_MANUAL_PATH" >&2; return 1; }
  [[ -f "$OFFICIAL_MANUAL_PATH" && -s "$OFFICIAL_MANUAL_PATH" ]] || { echo "official manual must be a non-empty file" >&2; return 1; }
  [[ "${OFFICIAL_MANUAL_PATH,,}" == *.pdf ]] || { echo "official manual must be a PDF" >&2; return 1; }
}

validate_real_image() {
  [[ -n "${REAL_IMAGE_PATH:-}" && -f "$REAL_IMAGE_PATH" && -s "$REAL_IMAGE_PATH" ]] || { echo "REAL_IMAGE_PATH must be a non-empty file" >&2; return 1; }
  case "${REAL_IMAGE_PATH,,}" in *.jpg|*.jpeg|*.png|*.webp) ;; *) echo "REAL_IMAGE_PATH must be jpg, jpeg, png, or webp" >&2; return 1 ;; esac
}

require_frontend() {
  if command -v npm >/dev/null 2>&1 && [[ -d frontend/node_modules ]]; then
    (cd frontend && npm run build) | tee "$RUN_DIR/frontend-build.log"
  elif [[ -f frontend/dist/index.html ]]; then
    echo "using explicitly prebuilt frontend/dist for $(git rev-parse HEAD)" | tee "$RUN_DIR/frontend-build.log"
  else
    echo "frontend build capability and prebuilt frontend/dist are both unavailable" >&2
    return 1
  fi
  FRONTEND_PASSED="true"
}

assert_provider_auth() {
  local status_file="$1"
  "$PYTHON_BIN" - "$status_file" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))["data"]
auth = data.get("auth") or data.get("system", {}).get("auth") or {}
assert auth.get("mode") == "token", auth
assert auth.get("valid") is True, auth
for key in ("adminConfigured", "reviewerConfigured", "operatorConfigured"):
    assert auth.get(key) is True, auth
PY
}

start_backend() {
  require_command curl
  [[ -x backend/.venv/bin/python ]] || { echo "backend/.venv/bin/python is required" >&2; return 1; }
  local runtime="$RUN_DIR/runtime"
  mkdir -p "$runtime/knowledge" "$runtime/uploads"
  (
    while IFS='=' read -r key value; do
      [[ -z "$key" || "$key" == \#* ]] && continue
      [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      export "$key=$value"
    done < "$ROOT_DIR/.env"
    export APP_KNOWLEDGE_DIR="$runtime/knowledge"
    export APP_UPLOAD_DIR="$runtime/uploads"
    export MINERU_ENABLED=false
    exec backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18000
  ) >"$RUN_DIR/backend-start.log" 2>&1 &
  BACKEND_PID=$!
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:18000/api/health >/dev/null 2>&1; then
      curl -fsS http://127.0.0.1:18000/api/providers/status >"$RUN_DIR/provider-status.json"
      assert_provider_auth "$RUN_DIR/provider-status.json"
      return 0
    fi
    sleep 1
  done
  echo "backend failed to start" >&2
  return 1
}

assert_status() {
  local expected="$1"; shift
  local actual
  actual="$(curl -sS -o /dev/null -w '%{http_code}' "$@")"
  [[ "$actual" == "$expected" ]] || { echo "expected HTTP $expected, got $actual" >&2; return 1; }
}

official_manual_smoke() {
  local base="$1" upload="$RUN_DIR/official-manual-upload.json" chunks="$RUN_DIR/official-manual-chunks.json"
  local search="$RUN_DIR/official-manual-search.json" rag="$RUN_DIR/official-manual-rag.json"
  curl -fsS -X POST "$base/api/knowledge/documents" -H "Authorization: Bearer $OPERATOR_TOKEN" \
    -F "file=@${OFFICIAL_MANUAL_PATH};type=application/pdf" -F 'source_name=摩托车发动机维修手册' >"$upload"
  OFFICIAL_DOCUMENT_ID="$("$PYTHON_BIN" - "$upload" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["data"]
assert d.get("id") and int(d.get("chunkCount", 0)) > 0 and d.get("status") == "pending_review", d
print(d["id"])
PY
)"
  curl -fsS "$base/api/knowledge/documents/$OFFICIAL_DOCUMENT_ID/chunks" -H "Authorization: Bearer $REVIEWER_TOKEN" >"$chunks"
  mapfile -t chunk_ids < <("$PYTHON_BIN" - "$chunks" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["data"]
items = d if isinstance(d, list) else d.get("items", d.get("chunks", []))
for item in items:
    if item.get("review_status") == "pending_review" and item.get("id"):
        print(item["id"])
PY
)
  [[ "${#chunk_ids[@]}" -gt 0 ]] || { echo "official manual has no pending chunks" >&2; return 1; }
  local approved=0 chunk_id
  for chunk_id in "${chunk_ids[@]}"; do
    curl -fsS -X PATCH "$base/api/knowledge/documents/$OFFICIAL_DOCUMENT_ID/chunks/$chunk_id/review" \
      -H "Authorization: Bearer $REVIEWER_TOKEN" -H 'Content-Type: application/json' \
      -d '{"action":"approve","reason":"LoongArch/Kylin target acceptance","reviewer":"target-acceptance"}' >/dev/null
    approved=$((approved + 1))
  done
  [[ "$approved" -gt 0 ]]
  curl -fsS -X POST "$base/api/search" -H 'Content-Type: application/json' \
    -d '{"deviceModel":"摩托车发动机","faultText":"无法启动 火花塞 点火系统","inputType":"text","topK":10}' >"$search"
  curl -fsS -X POST "$base/api/rag/answer" -H 'Content-Type: application/json' \
    -d '{"deviceModel":"摩托车发动机","faultText":"无法启动 火花塞 点火系统","inputType":"text","topK":10}' >"$rag"
  "$PYTHON_BIN" - "$OFFICIAL_DOCUMENT_ID" "$upload" "$search" "$rag" "$RUN_DIR/official-manual-smoke.json" "$approved" <<'PY'
import json, sys
doc_id, upload_path, search_path, rag_path, output_path, approved = sys.argv[1:]
upload = json.load(open(upload_path, encoding="utf-8"))["data"]
search = json.load(open(search_path, encoding="utf-8"))["data"]
rag = json.load(open(rag_path, encoding="utf-8"))["data"]
results = search.get("results", search if isinstance(search, list) else [])
hits = [x for x in results if (x.get("documentId") or x.get("sourceDocId")) == doc_id and x.get("sourceType") in {"document", "document_asset"}]
assert hits, results
assert rag.get("answerMode") in {"grounded", "grounded_with_caution", "insufficient_evidence"}, rag
citations = rag.get("citations") or []
matched = [x for x in citations if (x.get("documentId") or x.get("sourceDocId")) == doc_id]
assert matched and any(x.get("chunkId") or x.get("page") is not None or x.get("section") for x in matched), citations
summary = {"documentId": doc_id, "chunkCount": upload["chunkCount"], "approvedCount": int(approved), "searchHitCount": len(hits), "citationCount": len(matched)}
json.dump(summary, open(output_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
  local download="$RUN_DIR/official-manual-download.bin"
  curl -fsS "$base/api/knowledge/documents/$OFFICIAL_DOCUMENT_ID/file" -H "Authorization: Bearer $REVIEWER_TOKEN" -o "$download"
  [[ -s "$download" ]]
  rm -f "$download" "$chunks" "$search" "$rag"
  OFFICIAL_MANUAL_VERIFIED="true"
}

api_smoke() {
  require_command curl
  require_role_tokens || { echo "three role tokens are required for strict smoke" >&2; return 1; }
  local base="$1" upload_json upload_id case_json case_id feedback_json feedback_id
  assert_status 401 -X POST "$base/api/uploads"
  assert_status 401 -X POST "$base/api/uploads" -H 'Authorization: Bearer invalid'
  upload_json="$(curl -fsS -X POST "$base/api/uploads" -H "Authorization: Bearer $OPERATOR_TOKEN" -F 'file=@/etc/hosts;type=image/png;filename=fault.png')"
  upload_id="$(printf '%s' "$upload_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 "$base/api/uploads/$upload_id/file" -H "Authorization: Bearer $OPERATOR_TOKEN"
  assert_status 403 "$base/api/review/items" -H "Authorization: Bearer $OPERATOR_TOKEN"
  assert_status 200 "$base/api/review/items" -H "Authorization: Bearer $REVIEWER_TOKEN"
  assert_status 403 -X POST "$base/api/knowledge/graph/rebuild" -H "Authorization: Bearer $REVIEWER_TOKEN"
  assert_status 200 -X POST "$base/api/knowledge/graph/rebuild" -H "Authorization: Bearer $ADMIN_TOKEN"
  assert_status 404 "$base/uploads/$upload_id.png"
  assert_status 404 "$base/knowledge/files/missing.pdf"
  curl -fsS "$base/api/providers/status" >"$RUN_DIR/provider-status.json"
  assert_provider_auth "$RUN_DIR/provider-status.json"
  case_json="$(curl -fsS -X POST "$base/api/cases" -H "Authorization: Bearer $OPERATOR_TOKEN" -H 'Content-Type: application/json' -d '{"deviceModel":"engine-smoke","faultText":"smoke fault","cause":"smoke cause","solution":"smoke solution","result":"smoke result","tags":["smoke"]}')"
  case_id="$(printf '%s' "$case_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 -X PATCH "$base/api/cases/$case_id/review" -H "Authorization: Bearer $REVIEWER_TOKEN" -H 'Content-Type: application/json' -d '{"action":"approve","reviewNote":"smoke"}'
  feedback_json="$(curl -fsS -X POST "$base/api/rag/feedback" -H "Authorization: Bearer $OPERATOR_TOKEN" -H 'Content-Type: application/json' -d '{"deviceModel":"engine-smoke","faultText":"smoke fault","originalAnswer":"before","correctedAnswer":"after","labels":["smoke"],"reason":"smoke","reviewer":"operator"}')"
  feedback_id="$(printf '%s' "$feedback_json" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 -X PATCH "$base/api/rag/feedback/$feedback_id/review" -H "Authorization: Bearer $REVIEWER_TOKEN" -H 'Content-Type: application/json' -d '{"action":"approve","reviewNote":"smoke"}'
  AUTH_SMOKE_PASSED="true"
  official_manual_smoke "$base"
  API_SMOKE_PASSED="true"
  printf '{"result":"api-smoke-passed"}\n' >"$RUN_DIR/api-smoke.json"
}

check_real_providers() {
  local base="$1"
  if [[ "${REQUIRE_REAL_LLM:-false}" == "true" ]]; then
    curl -fsS -X POST "$base/api/rag/answer" -H 'Content-Type: application/json' \
      -d '{"deviceModel":"摩托车发动机","faultText":"无法启动 火花塞 点火系统","inputType":"text","topK":10}' >"$RUN_DIR/real-llm-response.json"
    curl -fsS "$base/api/providers/status" >"$RUN_DIR/provider-status.json"
    "$PYTHON_BIN" - "$RUN_DIR/real-llm-response.json" "$RUN_DIR/provider-status.json" "$OFFICIAL_DOCUMENT_ID" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["data"]
status = json.load(open(sys.argv[2], encoding="utf-8"))["data"]["llm"]
assert d.get("provider") not in {None, "", "mock"}, d
assert d.get("fallback") is False and d.get("rawAnswer") and d.get("answer"), d
assert d.get("answerMode") in {"grounded", "grounded_with_caution", "insufficient_evidence"}, d
assert d.get("citations") and any((x.get("documentId") or x.get("sourceDocId")) == sys.argv[3] for x in d["citations"]), d
assert status.get("effectiveProvider") != "mock" and status.get("keyConfigured") is True, status
PY
    REAL_LLM_VERIFIED="true"
  fi
  if [[ "${REQUIRE_REAL_MULTIMODAL:-false}" == "true" ]]; then
    validate_real_image
    curl -fsS -X POST "$base/api/multimodal/diagnosis" \
      -F 'deviceModel=摩托车发动机' -F 'faultText=请结合图片识别故障部件和异常现象' \
      -F 'maintenanceLevel=normal_repair' -F 'riskLevel=medium' -F "image=@${REAL_IMAGE_PATH}" \
      >"$RUN_DIR/real-multimodal-response.json"
    "$PYTHON_BIN" - "$RUN_DIR/real-multimodal-response.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["data"]
image = d.get("imageAnalysis") or {}
assert image and image.get("provider") not in {None, "", "mock", "mock-vision", "none"}, image
assert image.get("fallback") is False, image
context = d.get("queryContext") or {}
assert any((image.get(k) for k in ("summary", "observations", "detectedComponents", "visualSymptoms"))) or context.get("ocrText"), d
signals = d.get("multimodalSignals") or {}
assert signals.get("signalSource") not in {None, "", "mock", "none"}, signals
raw = d.get("raw") or {}
assert d.get("answerMode") == raw.get("answerMode"), d
assert d.get("finalAnswerSource") == raw.get("finalAnswerSource"), d
PY
    REAL_MULTIMODAL_VERIFIED="true"
  fi
}

run_venv() {
  require_command curl
  require_role_tokens
  APP_ENV=test AUTH_MODE=off ALLOW_INSECURE_AUTH_OFF=true \
    OFFICIAL_MANUAL_PATH="${OFFICIAL_MANUAL_PATH:-}" backend/.venv/bin/python -m pytest -q | tee "$RUN_DIR/backend-tests.log"
  BACKEND_TESTS_PASSED="true"
  require_frontend
  start_backend
  api_smoke http://127.0.0.1:18000 | tee "$RUN_DIR/auth-smoke.log"
  check_real_providers http://127.0.0.1:18000
}

build_docker_env() {
  local target="$1" key value
  local keys=(APP_ENV AUTH_MODE ALLOW_INSECURE_AUTH_OFF AUTH_OPERATOR_TOKEN AUTH_REVIEWER_TOKEN AUTH_ADMIN_TOKEN
    REMOTE_API_MODE LLM_PROVIDER OPENAI_BASE_URL OPENAI_API_STYLE OPENAI_MODEL OPENAI_API_KEY OPENAI_ENABLE_THINKING
    ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_API_KEY MULTIMODAL_PROVIDER MULTIMODAL_TIMEOUT_SECONDS
    MULTIMODAL_OPENAI_BASE_URL MULTIMODAL_OPENAI_API_KEY MULTIMODAL_OPENAI_MODEL MULTIMODAL_OPENAI_API_STYLE
    MULTIMODAL_OPENAI_ENABLE_THINKING MULTIMODAL_MAX_TOKENS MULTIMODAL_TEMPERATURE
    LOCAL_MULTIMODAL_BASE_URL LOCAL_MULTIMODAL_MODEL LOCAL_MULTIMODAL_API_KEY LOCAL_MULTIMODAL_MAX_TOKENS
    LOCAL_MULTIMODAL_TEMPERATURE OCR_PROVIDER RAG_VECTOR_STORE RAG_VECTOR_SQLITE_ENGINE RAG_VECTOR_ENHANCER
    RAG_VECTOR_FALLBACK_LOCAL)
  require_role_tokens
  for key in "${keys[@]}"; do
    case "$key" in APP_ENV) value=competition ;; AUTH_MODE) value=token ;; ALLOW_INSECURE_AUTH_OFF) value=false ;; *) value="$(config_value "$key")" ;; esac
    [[ -z "$value" ]] || printf '%s=%s\n' "$key" "$value"
  done >"$target"
  chmod 600 "$target"
}

run_docker() {
  require_command docker
  require_command curl
  [[ -f frontend/dist/index.html ]] || return 1
  docker build -t "$IMAGE_NAME" . | tee "$RUN_DIR/frontend-build.log"
  FRONTEND_PASSED="true"
  local test_args=(--rm -e APP_ENV=test -e AUTH_MODE=off -e ALLOW_INSECURE_AUTH_OFF=true -v "$ROOT_DIR/tests:/app/tests:ro")
  if [[ -n "${OFFICIAL_MANUAL_PATH:-}" ]]; then
    test_args+=(-e OFFICIAL_MANUAL_PATH=/fixtures/official-manual.pdf -v "$OFFICIAL_MANUAL_PATH:/fixtures/official-manual.pdf:ro")
  fi
  docker run "${test_args[@]}" "$IMAGE_NAME" python -m pytest -q | tee "$RUN_DIR/backend-tests.log"
  BACKEND_TESTS_PASSED="true"
  TEMP_DOCKER_ENV="$(mktemp "${TMPDIR:-/tmp}/software-cup-docker-env.XXXXXX")"
  build_docker_env "$TEMP_DOCKER_ENV"
  docker run -d --name "$CONTAINER_NAME" -p "${DOCKER_PORT}:8000" --env-file "$TEMP_DOCKER_ENV" "$IMAGE_NAME" >"$RUN_DIR/backend-start.log"
  rm -f "$TEMP_DOCKER_ENV"
  TEMP_DOCKER_ENV=""
  for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/health" >/dev/null
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/providers/status" >"$RUN_DIR/provider-status.json"
  assert_provider_auth "$RUN_DIR/provider-status.json"
  api_smoke "http://127.0.0.1:${DOCKER_PORT}" | tee "$RUN_DIR/auth-smoke.log"
  check_real_providers "http://127.0.0.1:${DOCKER_PORT}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preflight|--venv|--docker) [[ -z "$MODE" ]] || { usage; exit 2; }; MODE="$1" ;;
    --strict-target) STRICT_TARGET="true" ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ -n "$MODE" ]] || { usage; exit 2; }
select_python
new_evidence_dir
AUDIT_OS="unknown"
if [[ -f /etc/os-release ]]; then AUDIT_OS="$(tr '\n' ' ' </etc/os-release)"; fi
export AUDIT_GIT_SHA="$(git rev-parse HEAD)" AUDIT_ARCH="$(uname -m)" AUDIT_OS
export AUDIT_MODE="${MODE#--}" AUDIT_STRICT="$STRICT_TARGET"
preflight
if [[ "$STRICT_TARGET" == "true" ]]; then
  check_strict_target
  validate_official_manual
  [[ "${REQUIRE_REAL_MULTIMODAL:-false}" != "true" ]] || validate_real_image
fi
case "$MODE" in
  --preflight) exit 0 ;;
  --venv) run_venv ;;
  --docker) run_docker ;;
esac
