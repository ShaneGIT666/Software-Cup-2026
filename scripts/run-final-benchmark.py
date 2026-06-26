from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "testing" / "final-benchmark-results.json"


def run(command: list[str], timeout: int = 120) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "outputTail": completed.stdout[-4000:],
        }
    except Exception as exc:  # pragma: no cover - defensive runner path
        return {"command": command, "returncode": None, "ok": False, "error": str(exc)}


def main() -> int:
    checks = {
        "git_status": run(["git", "status", "--short", "--branch"], timeout=30),
        "git_diff_check": run(["git", "diff", "--check"], timeout=30),
        "official_smoke_tests": run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_official_compliance_smoke.py",
                "tests/test_multimodal_diagnosis.py",
                "tests/test_maintenance_workflow_guidance.py",
                "-q",
            ],
            timeout=180,
        ),
    }
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(item.get("ok") for item in checks.values()) else "failed",
        "checks": checks,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
