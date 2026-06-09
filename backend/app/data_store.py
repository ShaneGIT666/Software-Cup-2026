from __future__ import annotations

import json
import os
from uuid import uuid4
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
    _atomic_write_json(path, data)


def _read_knowledge_json(name: str) -> list[dict[str, Any]]:
    path = knowledge_dir() / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _read_knowledge_object(name: str) -> dict[str, Any]:
    path = knowledge_dir() / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_knowledge_json(name: str, data: list[dict[str, Any]]) -> None:
    path = knowledge_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, data)


def _write_knowledge_object(name: str, data: dict[str, Any]) -> None:
    path = knowledge_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json_value(path, data)


def _atomic_write_json(path: Path, data: list[dict[str, Any]]) -> None:
    _atomic_write_json_value(path, data)


def _atomic_write_json_value(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


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


def load_knowledge_revisions() -> list[dict[str, Any]]:
    return _read_knowledge_json("knowledge-revisions.json")


def save_knowledge_revisions(revisions: list[dict[str, Any]]) -> None:
    _write_knowledge_json("knowledge-revisions.json", revisions)


def load_knowledge_graph_cache() -> dict[str, Any]:
    return _read_knowledge_object("knowledge-graph.json")


def save_knowledge_graph_cache(graph: dict[str, Any]) -> None:
    _write_knowledge_object("knowledge-graph.json", graph)
