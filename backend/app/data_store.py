from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "data" / "examples"


def _read_json(name: str) -> list[dict[str, Any]]:
    path = EXAMPLES_DIR / name
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


@lru_cache(maxsize=1)
def load_seed_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "devices": _read_json("devices.json"),
        "manuals": _read_json("manuals.json"),
        "cases": _read_json("repair-cases.json"),
        "workflows": _read_json("workflows.json"),
    }
