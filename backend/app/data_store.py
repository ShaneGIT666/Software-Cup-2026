from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "data" / "examples"


def examples_dir() -> Path:
    configured = os.getenv("APP_EXAMPLES_DIR")
    return Path(configured) if configured else EXAMPLES_DIR


def upload_dir() -> Path:
    configured = os.getenv("APP_UPLOAD_DIR")
    return Path(configured) if configured else PROJECT_ROOT / "data" / "uploads"


def _read_json(name: str) -> list[dict[str, Any]]:
    path = examples_dir() / name
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _write_json(name: str, data: list[dict[str, Any]]) -> None:
    path = examples_dir() / name
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_seed_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "devices": _read_json("devices.json"),
        "manuals": _read_json("manuals.json"),
        "cases": _read_json("repair-cases.json"),
        "workflows": _read_json("workflows.json"),
    }


def load_cases() -> list[dict[str, Any]]:
    return _read_json("repair-cases.json")


def save_cases(cases: list[dict[str, Any]]) -> None:
    _write_json("repair-cases.json", cases)
