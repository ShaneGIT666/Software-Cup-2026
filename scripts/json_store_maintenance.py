from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def is_valid_json(path: Path) -> bool:
    try:
        load_json(path)
        return True
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def json_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for folder in (root / "data" / "examples", root / "data" / "knowledge"):
        if folder.exists():
            candidates.extend(path for path in folder.glob("*.json") if not path.name.endswith(".bak"))
    return sorted(candidates)


def scan_json_store(root: Path = PROJECT_ROOT, repair: bool = False) -> dict[str, Any]:
    files = json_files(root)
    results: list[dict[str, Any]] = []
    repaired_count = 0

    for path in files:
        relative_path = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        if is_valid_json(path):
            results.append({"path": relative_path, "status": "ok", "backup": str(backup_path(path))})
            continue

        backup = backup_path(path)
        if backup.exists() and is_valid_json(backup):
            if repair:
                shutil.copy2(backup, path)
                repaired_count += 1
                results.append({"path": relative_path, "status": "repaired", "backup": str(backup)})
            else:
                results.append({"path": relative_path, "status": "recoverable", "backup": str(backup)})
            continue

        results.append({"path": relative_path, "status": "corrupted", "backup": str(backup) if backup.exists() else ""})

    failing_statuses = {"recoverable", "corrupted"}
    success = not any(item["status"] in failing_statuses for item in results)
    return {
        "success": success,
        "mode": "repair" if repair else "check",
        "fileCount": len(files),
        "repairedCount": repaired_count,
        "issueCount": sum(1 for item in results if item["status"] != "ok"),
        "items": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and optionally repair JSON store files from .bak backups.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Repository root to scan.")
    parser.add_argument("--repair", action="store_true", help="Restore invalid JSON files from valid .bak backups.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = scan_json_store(args.root.resolve(), repair=args.repair)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
