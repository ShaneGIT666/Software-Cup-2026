from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    try:
        logging.disable(logging.CRITICAL)
        load_local_env()
        from backend.app.multimodal_adapter import multimodal_operational_probe, multimodal_readiness

        readiness = multimodal_readiness()
        probe = multimodal_operational_probe()
        record = {"readiness": readiness, "probe": probe}
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = TMP_ROOT / f"multimodal-provider-smoke-{stamp}.json"
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for key in ("provider", "model", "configReady", "probeOk", "status", "failureCategory"):
            print(f"{key}: {probe[key]}")
        return 0 if probe["probeOk"] else 1
    except Exception as exc:
        print(f"provider smoke failed safely: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
