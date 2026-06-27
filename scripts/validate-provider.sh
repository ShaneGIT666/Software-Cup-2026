#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:8000"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Validate backend provider status.

Usage:
  bash scripts/validate-provider.sh [http://127.0.0.1:8000]

The script calls /api/providers/status and never prints API keys.
EOF
  exit 0
fi

if [[ $# -gt 0 ]]; then
  BASE_URL="$1"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to request /api/providers/status."
  exit 1
fi

if ! response="$(curl -fsS "$BASE_URL/api/providers/status")"; then
  echo "Backend service is not available. Please confirm it is running."
  exit 1
fi

echo "Provider status JSON returned. Raw response follows; it does not include API keys:"
echo "$response"
