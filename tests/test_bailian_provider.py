from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import backend.app.llm_adapter as llm_adapter
import backend.app.multimodal_adapter as multimodal_adapter
from backend.app.provider_policy import provider_status


def context() -> dict[str, Any]:
    return {
        "id": "chunk-1",
        "title": "Ignition",
        "sourceType": "document",
        "sourceName": "manual",
        "snippet": "Inspect the spark plug and ignition system.",
        "confidence": 0.9,
        "documentId": "doc-1",
        "chunkId": "chunk-1",
        "reviewStatus": "approved",
    }


def configure_text(monkeypatch: pytest.MonkeyPatch, thinking: bool = False) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/compatible-mode/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen3.6-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setenv("OPENAI_ENABLE_THINKING", "true" if thinking else "false")


@pytest.mark.parametrize("thinking", (False, True))
def test_bailian_text_chat_payload(monkeypatch: pytest.MonkeyPatch, thinking: bool) -> None:
    configure_text(monkeypatch, thinking)
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured.update(url=url, headers=headers, payload=payload, timeout=timeout)
        return {"choices": [{"message": {"content": "model answer"}}]}

    monkeypatch.setattr(llm_adapter, "_post_json", fake_post)
    result = llm_adapter.real_rag_answer("engine", "cannot start", [context()], "openai")

    payload = captured["payload"]
    assert captured["url"].endswith("/chat/completions")
    assert payload["model"] == "qwen3.6-flash"
    assert payload["stream"] is False
    assert isinstance(payload["messages"][0]["content"], str)
    assert all(heading in payload["messages"][0]["content"] for heading in llm_adapter.REQUIRED_RAG_HEADINGS)
    assert "必须优先完整输出以下 11 个标题" in payload["messages"][0]["content"]
    assert "extra_body" not in payload
    assert payload.get("enable_thinking") is True if thinking else "enable_thinking" not in payload
    assert result["provider"] == "openai"
    assert result["fallback"] is False


def configure_multimodal(monkeypatch: pytest.MonkeyPatch, *, separate: bool = True) -> None:
    monkeypatch.setenv("MULTIMODAL_PROVIDER", "openai")
    monkeypatch.setenv("MULTIMODAL_OPENAI_API_STYLE", "chat_completions")
    if separate:
        monkeypatch.setenv("MULTIMODAL_OPENAI_BASE_URL", "https://provider.example/compatible-mode/v1")
        monkeypatch.setenv("MULTIMODAL_OPENAI_MODEL", "qwen3.6-flash")
        monkeypatch.setenv("MULTIMODAL_OPENAI_API_KEY", "test-only-key")


def test_bailian_multimodal_chat_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_multimodal(monkeypatch)
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nsmall-test-image")
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured.update(url=url, payload=payload)
        return {"choices": [{"message": {"content": "image analysis"}}]}

    monkeypatch.setattr(multimodal_adapter, "_post_json", fake_post)
    result = multimodal_adapter.real_multimodal_analysis(image, "sample", "png", "openai")

    payload = captured["payload"]
    content = payload["messages"][0]["content"]
    assert captured["url"].endswith("/chat/completions")
    assert not captured["url"].endswith("/responses")
    assert {item["type"] for item in content} == {"text", "image_url"}
    image_item = next(item for item in content if item["type"] == "image_url")
    assert image_item["image_url"]["url"].startswith("data:image/png;base64,")
    assert payload["stream"] is False
    assert result["provider"] == "openai"
    assert result["fallback"] is False


def test_multimodal_openai_config_falls_back_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_multimodal(monkeypatch, separate=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://fallback.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    monkeypatch.setenv("OPENAI_MODEL", "qwen3.6-flash")

    assert multimodal_adapter.multimodal_openai_base_url() == "https://fallback.example/v1"
    assert multimodal_adapter.multimodal_openai_api_key() == "fallback-key"
    assert multimodal_adapter.multimodal_openai_model() == "qwen3.6-flash"


def test_chat_completions_rejects_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_multimodal(monkeypatch)
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(RuntimeError, match="chat_completions multimodal accepts image input only"):
        multimodal_adapter.real_multimodal_analysis(pdf, "manual", "pdf", "openai")


def test_responses_multimodal_path_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_multimodal(monkeypatch)
    monkeypatch.setenv("MULTIMODAL_OPENAI_API_STYLE", "responses")
    image = tmp_path / "sample.png"
    image.write_bytes(b"png")
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        return {"output_text": "analysis"}

    monkeypatch.setattr(multimodal_adapter, "_post_json", fake_post)
    multimodal_adapter.real_multimodal_analysis(image, "sample", "png", "openai")
    assert captured["url"].endswith("/responses")


def test_provider_status_exposes_only_non_sensitive_bailian_config(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_text(monkeypatch)
    configure_multimodal(monkeypatch)
    status = provider_status()

    assert status["llm"] | {"model": "qwen3.6-flash", "apiStyle": "chat_completions"} == status["llm"]
    assert status["llm"]["thinkingEnabled"] is False
    assert status["multimodal"]["model"] == "qwen3.6-flash"
    assert status["multimodal"]["apiStyle"] == "chat_completions"
    assert status["multimodal"]["keyConfigured"] is True
    serialized = repr(status)
    assert "test-only-key" not in serialized
    assert "provider.example" not in serialized
