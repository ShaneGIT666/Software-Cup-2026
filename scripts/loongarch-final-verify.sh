#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="software-cup-final-verify:latest"
CONTAINER_NAME="software-cup-final-verify"
DOCKER_PORT="${DOCKER_PORT:-18080}"
API_PORTS=("8000" "18000")

export REMOTE_API_MODE="${REMOTE_API_MODE:-off}"
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export MULTIMODAL_PROVIDER="${MULTIMODAL_PROVIDER:-mock}"
export OCR_PROVIDER="${OCR_PROVIDER:-mock}"
export RAG_VECTOR_STORE="${RAG_VECTOR_STORE:-sqlite}"
export RAG_VECTOR_SQLITE_ENGINE="${RAG_VECTOR_SQLITE_ENGINE:-python_scan}"
export RAG_VECTOR_ENHANCER="${RAG_VECTOR_ENHANCER:-off}"
export RAG_VECTOR_FALLBACK_LOCAL="${RAG_VECTOR_FALLBACK_LOCAL:-on}"

TRANSFERABLE_TESTS=(
  tests/test_backend_api.py
  tests/test_evidence_pack.py
  tests/test_multimodal_diagnosis.py
  tests/test_multimodal_cross_modal_signals.py
  tests/test_rag_feedback_review_flow.py
  tests/test_maintenance_workflow_guidance.py
  tests/test_case_experience_review_flow.py
  tests/test_chunk_revision_audit.py
  tests/test_knowledge_graph_approved_only.py
  tests/test_official_compliance_smoke.py
)

section() {
  echo
  echo "== $1 =="
}

runtime_info() {
  section "System"
  date -Is
  uname -a || true
  printf "arch: "
  uname -m || true

  section "Runtime"
  if command -v python3 >/dev/null 2>&1; then python3 --version; else echo "python3: not found"; fi
  if [ -x "backend/.venv/bin/python" ]; then backend/.venv/bin/python --version; else echo "backend/.venv: not found"; fi
  if command -v node >/dev/null 2>&1; then node --version; else echo "node: not found"; fi
  if command -v npm >/dev/null 2>&1; then npm --version; else echo "npm: not found"; fi
  if command -v docker >/dev/null 2>&1; then docker --version; else echo "docker: not found"; fi

  section "Verification defaults"
  echo "REMOTE_API_MODE=${REMOTE_API_MODE}"
  echo "LLM_PROVIDER=${LLM_PROVIDER}"
  echo "MULTIMODAL_PROVIDER=${MULTIMODAL_PROVIDER}"
  echo "OCR_PROVIDER=${OCR_PROVIDER}"
  echo "RAG_VECTOR_STORE=${RAG_VECTOR_STORE}"
  echo "RAG_VECTOR_SQLITE_ENGINE=${RAG_VECTOR_SQLITE_ENGINE}"
  echo "RAG_VECTOR_ENHANCER=${RAG_VECTOR_ENHANCER}"
  echo "RAG_VECTOR_FALLBACK_LOCAL=${RAG_VECTOR_FALLBACK_LOCAL}"
}

python_bin() {
  if [ -x "backend/.venv/bin/python" ]; then
    echo "backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo ""
  fi
}

run_backend_tests() {
  section "Backend transferable tests"
  local py
  py="$(python_bin)"
  if [ -z "$py" ]; then
    echo "python unavailable, cannot run backend tests."
    return 2
  fi
  APP_EXAMPLES_DIR="$ROOT_DIR/data/examples" \
    APP_KNOWLEDGE_DIR="${TMPDIR:-/tmp}/software-cup-final-knowledge" \
    APP_UPLOAD_DIR="${TMPDIR:-/tmp}/software-cup-final-uploads" \
    MINERU_ENABLED=false \
    "$py" -m pytest "${TRANSFERABLE_TESTS[@]}" -q
}

run_frontend_build_if_possible() {
  section "Frontend build"
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm unavailable, skip frontend build. Install npm in target environment or use prebuilt frontend/dist."
    return 0
  fi
  if [ ! -d "frontend/node_modules" ]; then
    echo "frontend/node_modules missing, skip frontend build. Run npm ci/npm install before this step."
    return 0
  fi
  (cd frontend && npm run build)
}

run_static_checks() {
  section "Static checks"
  if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    git diff --check
  else
    echo "git unavailable or .git missing, skip git diff --check."
  fi
}

pick_running_api() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  for port in "${API_PORTS[@]}"; do
    if curl -fsS "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
      echo "http://127.0.0.1:${port}"
      return 0
    fi
  done
  return 1
}

run_api_smoke() {
  section "API smoke"
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl unavailable, skip API smoke."
    return 0
  fi

  local base_url
  if ! base_url="$(pick_running_api)"; then
    echo "backend not running on 8000 or 18000. Start backend first to run API smoke."
    return 0
  fi
  echo "Using API: ${base_url}"

  curl -fsS "${base_url}/api/health"
  echo
  curl -fsS "${base_url}/api/providers/status" | head -c 1200
  echo

  curl -fsS -X POST "${base_url}/api/search" \
    -H "Content-Type: application/json" \
    -d '{"deviceModel":"发动机-示例型号 A","faultText":"启动困难 怠速不稳","maintenanceLevel":"normal_repair","riskLevel":"medium","topK":5}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('search_results', len(d.get('results', [])))"

  curl -fsS -X POST "${base_url}/api/rag/answer" \
    -H "Content-Type: application/json" \
    -d '{"deviceModel":"发动机-示例型号 A","faultText":"启动困难 怠速不稳","maintenanceLevel":"normal_repair","riskLevel":"medium","topK":5}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('rag_provider', d.get('provider'), 'fallback', d.get('fallback'), 'citations', len(d.get('citations', [])), 'has_compliance', 'complianceChecks' in d.get('structuredAnswer', {}))"

  local sample_image
  sample_image="${TMPDIR:-/tmp}/software-cup-fault.png"
  printf "fake-image" > "$sample_image"
  curl -fsS -X POST "${base_url}/api/multimodal/diagnosis" \
    -F "deviceModel=发动机-示例型号 A" \
    -F "faultText=启动困难 怠速不稳" \
    -F "maintenanceLevel=emergency" \
    -F "riskLevel=critical" \
    -F "image=@${sample_image};type=image/png;filename=fault.png" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; s=d.get('multimodalSignals',{}); print('diagnosis_provider', d.get('provider'), 'fallback', d.get('fallback'), 'citations', len(d.get('citations', [])), 'level', d.get('queryContext', {}).get('maintenanceLevel'), 'cross_modal', s.get('matchMode'))"

  local feedback_id
  feedback_id="$(
    curl -fsS -X POST "${base_url}/api/rag/feedback" \
      -H "Content-Type: application/json" \
      -d '{"deviceModel":"发动机-示例型号 A","faultText":"启动困难 怠速不稳","maintenanceLevel":"normal_repair","originalAnswer":"脚本冒烟原始回答","correctedAnswer":"先复核燃油压力和点火系统，再决定维修步骤。","labels":["脚本冒烟","人工修正"],"reason":"补充检查顺序","reviewer":"loongarch-script"}' \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['id'])"
  )"
  echo "rag_feedback_created ${feedback_id}"
  curl -fsS "${base_url}/api/rag/feedback?status=pending_review" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('pending_feedback', d.get('total'))"
  curl -fsS -X PATCH "${base_url}/api/rag/feedback/${feedback_id}/review" \
    -H "Content-Type: application/json" \
    -d '{"action":"approve","reviewer":"loongarch-reviewer","reviewNote":"script smoke approved"}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('rag_feedback_reviewed', d.get('status'))"
  curl -fsS "${base_url}/api/knowledge/graph" \
    | FEEDBACK_ID="$feedback_id" python3 -c "import sys,json,os; d=json.load(sys.stdin)['data']; target='rag_feedback:' + os.environ['FEEDBACK_ID']; ids={n.get('id') for n in d.get('nodes', [])}; print('graph_nodes', len(ids), 'approved_only', d.get('approvedOnly'), 'has_feedback', target in ids); raise SystemExit(0 if target in ids else 1)"
}

docker_cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

run_docker_mode() {
  runtime_info
  section "Docker verification"
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker unavailable. Install Docker or use default venv verification mode."
    return 2
  fi
  if [ ! -d "frontend/dist" ]; then
    echo "frontend/dist missing. Run frontend build before docker mode because Dockerfile copies frontend/dist."
    return 2
  fi

  docker_cleanup
  trap docker_cleanup EXIT

  docker build --build-arg INSTALL_CHROMA=false -t "$IMAGE_NAME" .
  docker run -d --name "$CONTAINER_NAME" \
    -p "${DOCKER_PORT}:8000" \
    -e REMOTE_API_MODE=off \
    -e LLM_PROVIDER=mock \
    -e MULTIMODAL_PROVIDER=mock \
    -e OCR_PROVIDER=mock \
    -e RAG_VECTOR_STORE=sqlite \
    -e RAG_VECTOR_SQLITE_ENGINE=python_scan \
    -e RAG_VECTOR_ENHANCER=off \
    -e RAG_VECTOR_FALLBACK_LOCAL=on \
    "$IMAGE_NAME"

  sleep 5
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/health"
  echo
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/api/providers/status" | head -c 1200
  echo
  curl -fsS "http://127.0.0.1:${DOCKER_PORT}/" | head -c 200
  echo

  section "Docker logs tail"
  docker logs --tail 80 "$CONTAINER_NAME"
  docker_cleanup
  trap - EXIT
  echo "Docker verification completed."
}

run_default_mode() {
  runtime_info
  run_backend_tests
  run_frontend_build_if_possible
  run_static_checks
  run_api_smoke
  section "Summary"
  echo "Default verification completed. If API smoke was skipped, start backend and rerun this script."
}

case "${1:-}" in
  --docker)
    run_docker_mode
    ;;
  "" )
    run_default_mode
    ;;
  * )
    echo "Usage: bash scripts/loongarch-final-verify.sh [--docker]"
    exit 2
    ;;
esac
