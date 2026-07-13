from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ENDPOINTS = (
    "/api/providers/status",
    "/api/knowledge/documents",
    "/api/knowledge/parse-tasks",
    "/api/review/items?status=pending_review",
    "/api/cases",
    "/api/knowledge/graph",
    "/api/review/events?limit=100",
)


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip())


def item_count(data: Any) -> int | str:
    if isinstance(data, list):
        return len(data)
    if not isinstance(data, dict):
        return "-"
    if isinstance(data.get("items"), list):
        return len(data["items"])
    if isinstance(data.get("nodes"), list):
        return len(data["nodes"])
    return "-"


def error_category(status_code: int) -> str:
    if status_code == 200:
        return "none"
    if status_code in (401, 403):
        return "authorization"
    if status_code == 503:
        return "configuration"
    if status_code >= 500:
        return "server"
    return "http"


def main() -> int:
    load_local_env()
    from fastapi.testclient import TestClient

    from backend.app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    rows: list[tuple[str, int, bool, int | str, str]] = []
    for endpoint in ENDPOINTS:
        try:
            response = client.get(endpoint)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            success = response.status_code == 200 and bool(payload.get("success"))
            rows.append((endpoint, response.status_code, success, item_count(payload.get("data")), error_category(response.status_code)))
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            rows.append((endpoint, 0, False, "-", type(exc).__name__))

    print(f"{'endpoint':52} {'statusCode':>10} {'success':>7} {'itemCount':>9} errorCategory")
    for endpoint, status_code, success, count, category in rows:
        print(f"{endpoint:52} {status_code:>10} {str(success).lower():>7} {str(count):>9} {category}")

    passed = all(status_code == 200 and success for _, status_code, success, _, _ in rows)
    print("MANAGEMENT_CENTER_SMOKE_GO" if passed else "MANAGEMENT_CENTER_SMOKE_NO_GO")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

