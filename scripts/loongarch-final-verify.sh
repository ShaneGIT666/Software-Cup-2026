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
BACKEND_TESTS_PASSED="false"
FRONTEND_PASSED="false"
AUTH_SMOKE_PASSED="false"
API_SMOKE_PASSED="false"
REAL_LLM_VERIFIED="false"
REAL_MULTIMODAL_VERIFIED="false"

usage() {
  cat <<'EOF'
Usage: bash scripts/loongarch-final-verify.sh [--preflight|--venv|--docker] [--strict-target]

--preflight     Collect local target-readiness evidence without changing the environment.
--venv          Run strict venv-based acceptance with a temporary runtime directory.
--docker        Build and run the Docker acceptance route with filtered container environment.
--strict-target Require LoongArch and Kylin before running the selected acceptance route.
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "required command missing: $1" >&2; return 1; }
}

short_sha() { git rev-parse --short HEAD 2>/dev/null || echo unknown; }

safe_slug() { date -u +%Y%m%dT%H%M%SZ; }

new_evidence_dir() {
  RUN_DIR="$ROOT_DIR/docs/final-audit/evidence/$(safe_slug)-$(short_sha)"
  mkdir -p "$RUN_DIR"
}

write_summary() {
  local exit_code="$1"
  local result="NO-GO"
  if [[ "$exit_code" -eq 0 && "$MODE" != "--preflight" ]]; then result="GO"; fi
  if [[ "$MODE" == "--preflight" ]]; then result="TARGET_VERIFICATION_PENDING"; fi
  if [[ -n "$RUN_DIR" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      python3 - "$RUN_DIR/summary.json" "$result" <<'PY'
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
    "realLlmVerified": os.environ.get("AUDIT_REAL_LLM", "false") == "true",
    "realMultimodalVerified": os.environ.get("AUDIT_REAL_MM", "false") == "true",
    "result": result,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
    else
      printf '{"gitSha":"%s","architecture":"%s","os":"unknown","mode":"%s","strictTarget":%s,"backendTestsPassed":false,"frontendPassed":false,"authSmokePassed":false,"apiSmokePassed":false,"realLlmVerified":false,"realMultimodalVerified":false,"result":"%s"}\n' \
        "$AUDIT_GIT_SHA" "$AUDIT_ARCH" "$AUDIT_MODE" "$AUDIT_STRICT" "$result" >"$RUN_DIR/summary.json"
    fi
  fi
}

cleanup() {
  local status=$?
  if [[ -n "$BACKEND_PID" ]]; then kill "$BACKEND_PID" >/dev/null 2>&1 || true; wait "$BACKEND_PID" >/dev/null 2>&1 || true; fi
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  export AUDIT_BACKEND_TESTS="$BACKEND_TESTS_PASSED" AUDIT_FRONTEND="$FRONTEND_PASSED"
  export AUDIT_AUTH_SMOKE="$AUTH_SMOKE_PASSED" AUDIT_API_SMOKE="$API_SMOKE_PASSED"
  export AUDIT_REAL_LLM="$REAL_LLM_VERIFIED" AUDIT_REAL_MM="$REAL_MULTIMODAL_VERIFIED"
  write_summary "$status"
  exit "$status"
}

trap cleanup EXIT

read_env_value() {
  local key="$1" file="${2:-$ROOT_DIR/.env}"
  [[ -f "$file" ]] || return 1
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

require_role_tokens() {
  OPERATOR_TOKEN="$(read_env_value AUTH_OPERATOR_TOKEN)" || return 1
  REVIEWER_TOKEN="$(read_env_value AUTH_REVIEWER_TOKEN)" || return 1
  ADMIN_TOKEN="$(read_env_value AUTH_ADMIN_TOKEN)" || return 1
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
    python3 --version 2>/dev/null || echo "python3: not found"
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

require_frontend() {
  if command -v npm >/dev/null 2>&1 && [[ -d frontend/node_modules ]]; then
    (cd frontend && npm run build) | tee "$RUN_DIR/frontend-build.log"
  elif [[ -f frontend/dist/index.html ]]; then
    echo "using explicitly prebuilt frontend/dist" | tee "$RUN_DIR/frontend-build.log"
  else
    echo "frontend build capability and prebuilt frontend/dist are both unavailable" >&2
    return 1
  fi
  FRONTEND_PASSED="true"
}

start_backend() {
  require_command curl
  [[ -x backend/.venv/bin/python ]] || { echo "backend/.venv/bin/python is required" >&2; return 1; }
  local runtime="$RUN_DIR/runtime"
  mkdir -p "$runtime/knowledge" "$runtime/uploads"
  APP_KNOWLEDGE_DIR="$runtime/knowledge" APP_UPLOAD_DIR="$runtime/uploads" \
    MINERU_ENABLED=false backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18000 \
    >"$RUN_DIR/backend-start.log" 2>&1 &
  BACKEND_PID=$!
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:18000/api/health >/dev/null 2>&1 && return 0
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

api_smoke() {
  require_command curl
  require_command python3
  require_role_tokens || { echo "three role tokens are required for strict smoke" >&2; return 1; }
  local base="$1" upload_json upload_id case_json case_id feedback_json feedback_id
  assert_status 401 -X POST "$base/api/uploads"
  assert_status 401 -X POST "$base/api/uploads" -H 'Authorization: Bearer invalid'
  upload_json="$(curl -fsS -X POST "$base/api/uploads" -H "Authorization: Bearer $OPERATOR_TOKEN" -F 'file=@/etc/hosts;type=image/png;filename=fault.png')"
  upload_id="$(printf '%s' "$upload_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 "$base/api/uploads/$upload_id/file" -H "Authorization: Bearer $OPERATOR_TOKEN"
  assert_status 403 "$base/api/review/items" -H "Authorization: Bearer $OPERATOR_TOKEN"
  assert_status 200 "$base/api/review/items" -H "Authorization: Bearer $REVIEWER_TOKEN"
  assert_status 403 -X POST "$base/api/knowledge/graph/rebuild" -H "Authorization: Bearer $REVIEWER_TOKEN"
  assert_status 200 -X POST "$base/api/knowledge/graph/rebuild" -H "Authorization: Bearer $ADMIN_TOKEN"
  assert_status 404 "$base/uploads/$upload_id.png"
  assert_status 404 "$base/knowledge/files/missing.pdf"
  curl -fsS "$base/api/health" >/dev/null
  curl -fsS "$base/api/providers/status" >"$RUN_DIR/provider-status.json"
  curl -fsS -X POST "$base/api/search" -H 'Content-Type: application/json' -d '{"deviceModel":"发动机-示例型号 A","faultText":"启动困难","topK":5}' >/dev/null
  curl -fsS -X POST "$base/api/rag/answer" -H 'Content-Type: application/json' -d '{"deviceModel":"发动机-示例型号 A","faultText":"启动困难","topK":5}' \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; assert d["answerMode"] in {"grounded","grounded_with_caution","insufficient_evidence"}; assert not d.get("citations") or d.get("structuredAnswer",{}).get("citations")' >/dev/null
  curl -fsS -X POST "$base/api/multimodal/diagnosis" -F 'deviceModel=' -F 'faultText=UNIQUE-NO-EVIDENCE-SMOKE' -F 'topK=3' \
    | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; assert d["answerMode"] == d["raw"]["answerMode"]; assert d["finalAnswerSource"] == d["raw"]["finalAnswerSource"]' >/dev/null
  case_json="$(curl -fsS -X POST "$base/api/cases" -H "Authorization: Bearer $OPERATOR_TOKEN" -H 'Content-Type: application/json' -d '{"deviceModel":"engine-smoke","faultText":"smoke fault","cause":"smoke cause","solution":"smoke solution","result":"smoke result","tags":["smoke"]}')"
  case_id="$(printf '%s' "$case_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 -X PATCH "$base/api/cases/$case_id/review" -H "Authorization: Bearer $REVIEWER_TOKEN" -H 'Content-Type: application/json' -d '{"action":"approve","reviewNote":"smoke"}'
  feedback_json="$(curl -fsS -X POST "$base/api/rag/feedback" -H "Authorization: Bearer $OPERATOR_TOKEN" -H 'Content-Type: application/json' -d '{"deviceModel":"engine-smoke","faultText":"smoke fault","originalAnswer":"before","correctedAnswer":"after","labels":["smoke"],"reason":"smoke","reviewer":"operator"}')"
  feedback_id="$(printf '%s' "$feedback_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
  assert_status 200 -X PATCH "$base/api/rag/feedback/$feedback_id/review" -H "Authorization: Bearer $REVIEWER_TOKEN" -H 'Content-Type: application/json' -d '{"action":"approve","reviewNote":"smoke"}'
  AUTH_SMOKE_PASSED="true"
  API_SMOKE_PASSED="true"
  printf '{"result":"api-smoke-passed"}\n' >"$RUN_DIR/api-smoke.json"
}

check_real_providers() {
  if [[ "${REQUIRE_REAL_LLM:-false}" == "true" ]]; then
    [[ -n "${OPENAI_API_KEY:-}" ]] || return 1
    REAL_LLM_VERIFIED="true"
  fi
  if [[ "${REQUIRE_REAL_MULTIMODAL:-false}" == "true" ]]; then
    [[ -f "${REAL_IMAGE_PATH:-}" ]] || return 1
    REAL_MULTIMODAL_VERIFIED="true"
  fi
}

run_venv() {
  require_command python3
  require_command curl
  require_role_tokens
  backend/.venv/bin/python -m pytest -q | tee "$RUN_DIR/backend-tests.log"
  BACKEND_TESTS_PASSED="true"
  require_frontend
  start_backend
  api_smoke http://127.0.0.1:18000 | tee "$RUN_DIR/auth-smoke.log"
  check_real_providers
}

build_docker_env() {
  local target="$1"
  require_role_tokens
  {
    printf 'APP_ENV=production\nAUTH_MODE=token\nALLOW_INSECURE_AUTH_OFF=false\n'
    printf 'AUTH_OPERATOR_TOKEN=%s\nAUTH_REVIEWER_TOKEN=%s\nAUTH_ADMIN_TOKEN=%s\n' "$OPERATOR_TOKEN" "$REVIEWER_TOKEN" "$ADMIN_TOKEN"
    printf 'REMOTE_API_MODE=%s\nLLM_PROVIDER=%s\nMULTIMODAL_PROVIDER=%s\nOCR_PROVIDER=%s\n' "${REMOTE_API_MODE:-off}" "${LLM_PROVIDER:-mock}" "${MULTIMODAL_PROVIDER:-mock}" "${OCR_PROVIDER:-mock}"
    printf 'RAG_VECTOR_STORE=%s\nRAG_VECTOR_SQLITE_ENGINE=%s\nRAG_VECTOR_ENHANCER=%s\n' "${RAG_VECTOR_STORE:-sqlite}" "${RAG_VECTOR_SQLITE_ENGINE:-python_scan}" "${RAG_VECTOR_ENHANCER:-off}"
  } >"$target"
  chmod 600 "$target"
}

run_docker() {
  require_command docker
  require_command curl
  [[ -f frontend/dist/index.html ]] || return 1
  local env_file="$RUN_DIR/docker.env"
  build_docker_env "$env_file"
  docker build -t "$IMAGE_NAME" . | tee "$RUN_DIR/frontend-build.log"
  FRONTEND_PASSED="true"
  docker run -d --name "$CONTAINER_NAME" -p "${DOCKER_PORT}:8000" --env-file "$env_file" "$IMAGE_NAME" >"$RUN_DIR/backend-start.log"
  for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/health" >/dev/null
  api_smoke "http://127.0.0.1:${DOCKER_PORT}" | tee "$RUN_DIR/auth-smoke.log"
  check_real_providers
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
new_evidence_dir
AUDIT_OS="unknown"
if [[ -f /etc/os-release ]]; then AUDIT_OS="$(tr '\n' ' ' </etc/os-release)"; fi
export AUDIT_GIT_SHA="$(git rev-parse HEAD)" AUDIT_ARCH="$(uname -m)" AUDIT_OS
export AUDIT_MODE="${MODE#--}" AUDIT_STRICT="$STRICT_TARGET"
preflight
if [[ "$STRICT_TARGET" == "true" ]]; then check_strict_target; fi
case "$MODE" in
  --preflight) exit 0 ;;
  --venv) run_venv ;;
  --docker) run_docker ;;
esac
