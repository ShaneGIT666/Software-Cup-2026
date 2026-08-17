#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PATH="$ROOT/.env"
GITIGNORE_PATH="$ROOT/.gitignore"
MODE=""
BASE_URL=""
MODEL=""
API_KEY=""
FORCE="false"

show_help() {
  cat <<'EOF'
Initialize legacy prototype Provider/mock configuration only.

WARNING: this script does not generate PostgreSQL, M1 identity, idempotency,
controlled-storage, or production deployment configuration.

Usage:
  bash scripts/init-config.sh --mode offline
  bash scripts/init-config.sh --mode llm --base-url <url> --model <model>

Modes:
  offline  Demo fallback mode without remote API keys.
  llm      Real OpenAI-compatible LLM mode.

Safety:
  The script writes only local .env, backs up existing .env first, and masks API keys in output.
EOF
}

mask_key() {
  local key="${1:-}"
  if [[ -z "$key" ]]; then
    printf 'not configured'
  elif [[ ${#key} -le 8 ]]; then
    printf '****'
  else
    printf '%s****%s' "${key:0:3}" "${key: -4}"
  fi
}

ensure_gitignore() {
  if [[ ! -f "$GITIGNORE_PATH" ]]; then
    printf '.env\n.env.*\n!.env.example\n' > "$GITIGNORE_PATH"
    return
  fi
  grep -qxF '.env' "$GITIGNORE_PATH" || printf '\n# Local environment\n.env\n' >> "$GITIGNORE_PATH"
  grep -qxF '.env.*' "$GITIGNORE_PATH" || printf '.env.*\n' >> "$GITIGNORE_PATH"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      show_help
      exit 1
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "WARNING: legacy prototype configuration only; not a product or production initializer." >&2
  echo "Select run mode:"
  echo "  1. Offline demo fallback"
  echo "  2. Real LLM"
  read -r -p "Enter 1 or 2: " choice
  if [[ "$choice" == "2" ]]; then
    MODE="llm"
  else
    MODE="offline"
  fi
fi

if [[ "$MODE" != "offline" && "$MODE" != "llm" ]]; then
  echo "Mode must be offline or llm."
  exit 1
fi

ensure_gitignore

if [[ -f "$ENV_PATH" && "$FORCE" != "true" ]]; then
  read -r -p ".env already exists. Type yes to back it up and overwrite: " confirm
  if [[ "$confirm" != "yes" ]]; then
    echo "Cancelled. .env was not modified."
    exit 0
  fi
fi

if [[ -f "$ENV_PATH" ]]; then
  backup="$ROOT/.env.backup.$(date +%Y%m%d%H%M%S)"
  cp "$ENV_PATH" "$backup"
  echo "Backed up existing .env to $backup"
fi

if [[ "$MODE" == "llm" ]]; then
  [[ -n "$BASE_URL" ]] || read -r -p "OpenAI-compatible Base URL: " BASE_URL
  [[ -n "$MODEL" ]] || read -r -p "Model name: " MODEL
  if [[ -z "$API_KEY" ]]; then
    read -r -s -p "API Key: " API_KEY
    echo
  fi
  cat > "$ENV_PATH" <<EOF
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_BASE_URL=$BASE_URL
OPENAI_API_STYLE=chat_completions
OPENAI_MODEL=$MODEL
OPENAI_API_KEY=$API_KEY
LLM_TIMEOUT_SECONDS=60
RAG_USE_STRUCTURED_LLM_ANSWER=true
MULTIMODAL_PROVIDER=mock
OCR_PROVIDER=mock
RAG_VECTOR_FALLBACK_LOCAL=on
EOF
else
  cat > "$ENV_PATH" <<'EOF'
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
OCR_PROVIDER=mock
RAG_VECTOR_FALLBACK_LOCAL=on
EOF
fi

echo
echo "Local .env has been written."
echo "Summary:"
echo "  Mode: $MODE"
if [[ "$MODE" == "llm" ]]; then
  echo "  Base URL: $BASE_URL"
  echo "  Model: $MODEL"
else
  echo "  Base URL: not used"
  echo "  Model: mock"
fi
echo "  API Key: $(mask_key "$API_KEY")"
echo
echo "No supported Linux product start entry exists in this repository."
echo "This script only configures the legacy Provider/mock prototype; see scripts/README.md."
echo
echo "Validate provider status:"
echo "  bash scripts/validate-provider.sh"
echo "  Or open /api/providers/status and the System Status page."
echo
echo "Restore offline demo fallback:"
echo "  bash scripts/init-config.sh --mode offline --force"
