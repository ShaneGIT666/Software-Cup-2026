from __future__ import annotations

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
