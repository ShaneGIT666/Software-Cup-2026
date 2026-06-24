from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from backend.app import data_store, vector_store


def test_app_data_directories_use_app_prefixed_env_vars(monkeypatch, tmp_path) -> None:
    old_upload = tmp_path / "old-upload"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///should-not-be-used.db")
    monkeypatch.setenv("UPLOAD_DIR", str(old_upload))
    monkeypatch.delenv("APP_EXAMPLES_DIR", raising=False)
    monkeypatch.delenv("APP_UPLOAD_DIR", raising=False)
    monkeypatch.delenv("APP_KNOWLEDGE_DIR", raising=False)

    assert data_store.upload_dir() != old_upload
    assert data_store.examples_dir() == data_store.EXAMPLES_DIR
    assert data_store.knowledge_dir() == data_store.KNOWLEDGE_DIR

    examples = tmp_path / "examples"
    uploads = tmp_path / "uploads"
    knowledge = tmp_path / "knowledge"
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(examples))
    monkeypatch.setenv("APP_UPLOAD_DIR", str(uploads))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(knowledge))

    assert data_store.examples_dir() == examples
    assert data_store.upload_dir() == uploads
    assert data_store.knowledge_dir() == knowledge


def test_embedding_provider_uses_openai_compatible_embedding_endpoint(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post_json_positional(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["url"] = args[0]
        captured["payload"] = kwargs["payload"]
        captured["headers"] = kwargs["headers"]
        captured["timeout"] = kwargs["timeout"]
        return {"data": [{"embedding": [0.1, 0.2]}]}

    monkeypatch.setenv("REMOTE_API_MODE", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "embedding-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible.example/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "provider-specific-embedding")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr(vector_store, "_post_json", fake_post_json_positional)

    vectors = vector_store.openai_embed_texts(["发动机启动困难"])

    assert vectors == [[0.1, 0.2]]
    assert captured["url"] == "https://compatible.example/v1/embeddings"
    assert captured["payload"] == {"model": "provider-specific-embedding", "input": ["发动机启动困难"]}
    assert captured["headers"]["Authorization"] == "Bearer embedding-key"
    assert captured["timeout"] == 7


def test_default_embedding_model_is_openai_specific(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

    assert vector_store.embedding_model() == "text-embedding-3-small"


def test_env_example_matches_runtime_configuration_contract() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "APP_EXAMPLES_DIR=" in env_example
    assert "APP_UPLOAD_DIR=" in env_example
    assert "APP_KNOWLEDGE_DIR=" in env_example
    assert "DATABASE_URL=" not in env_example
    assert "\nUPLOAD_DIR=" not in env_example
    assert "RAG_EMBEDDING_PROVIDER=openai" in env_example
    assert "text-embedding-3-small is the OpenAI default only" in env_example
    assert "OpenAI-compatible providers must set their own embedding model" in env_example


def test_json_store_recovers_from_last_backup(monkeypatch, tmp_path) -> None:
    knowledge = tmp_path / "knowledge"
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(knowledge))

    data_store.save_documents([{"id": "first-good"}])
    data_store.save_documents([{"id": "second-good"}])

    documents_path = knowledge / "documents.json"
    backup_path = knowledge / "documents.json.bak"
    assert backup_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == [{"id": "first-good"}]

    documents_path.write_text("{not-valid-json", encoding="utf-8")

    assert data_store.load_documents() == [{"id": "first-good"}]

    data_store.save_documents([{"id": "third-good"}])
    assert data_store.load_documents() == [{"id": "third-good"}]
    assert json.loads(backup_path.read_text(encoding="utf-8")) == [{"id": "first-good"}]


def load_json_store_maintenance_module() -> Any:
    module_path = Path("scripts/json_store_maintenance.py")
    spec = importlib.util.spec_from_file_location("json_store_maintenance", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_json_store_maintenance_reports_recoverable_and_corrupted_files(tmp_path) -> None:
    maintenance = load_json_store_maintenance_module()
    examples = tmp_path / "data" / "examples"
    examples.mkdir(parents=True)
    (examples / "good.json").write_text('[{"id": "ok"}]\n', encoding="utf-8")
    (examples / "recoverable.json").write_text("{broken", encoding="utf-8")
    (examples / "recoverable.json.bak").write_text('[{"id": "backup"}]\n', encoding="utf-8")
    (examples / "corrupted.json").write_text("{broken", encoding="utf-8")
    (examples / "corrupted.json.bak").write_text("{also-broken", encoding="utf-8")

    report = maintenance.scan_json_store(tmp_path, repair=False)

    statuses = {item["path"].replace("\\", "/"): item["status"] for item in report["items"]}
    assert report["success"] is False
    assert statuses["data/examples/good.json"] == "ok"
    assert "recoverable" in statuses.values()
    assert "corrupted" in statuses.values()


def test_json_store_maintenance_repairs_from_valid_backup(tmp_path) -> None:
    maintenance = load_json_store_maintenance_module()
    examples = tmp_path / "data" / "examples"
    examples.mkdir(parents=True)
    target = examples / "recoverable.json"
    target.write_text("{broken", encoding="utf-8")
    (examples / "recoverable.json.bak").write_text('[{"id": "backup"}]\n', encoding="utf-8")

    report = maintenance.scan_json_store(tmp_path, repair=True)

    assert report["success"] is True
    assert report["repairedCount"] == 1
    assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "backup"}]
