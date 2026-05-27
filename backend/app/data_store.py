from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "data" / "examples"
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"


def examples_dir() -> Path:
    configured = os.getenv("APP_EXAMPLES_DIR")
    return Path(configured) if configured else EXAMPLES_DIR


def upload_dir() -> Path:
    configured = os.getenv("APP_UPLOAD_DIR")
    return Path(configured) if configured else PROJECT_ROOT / "data" / "uploads"


def knowledge_dir() -> Path:
    configured = os.getenv("APP_KNOWLEDGE_DIR")
    return Path(configured) if configured else KNOWLEDGE_DIR


def chroma_dir() -> Path:
    configured = os.getenv("APP_CHROMA_DIR")
    return Path(configured) if configured else knowledge_dir() / "chroma"


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


def _read_knowledge_json(name: str) -> list[dict[str, Any]]:
    path = knowledge_dir() / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _write_knowledge_json(name: str, data: list[dict[str, Any]]) -> None:
    path = knowledge_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
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


def load_documents() -> list[dict[str, Any]]:
    return _read_knowledge_json("documents.json")


def save_documents(documents: list[dict[str, Any]]) -> None:
    _write_knowledge_json("documents.json", documents)


def load_document_chunks() -> list[dict[str, Any]]:
    return _read_knowledge_json("document-chunks.json")


def save_document_chunks(chunks: list[dict[str, Any]]) -> None:
    _write_knowledge_json("document-chunks.json", chunks)
