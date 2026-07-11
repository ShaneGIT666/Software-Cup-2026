from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import backend.app.llm_adapter as llm_adapter
import backend.app.knowledge as knowledge
import backend.app.multimodal_adapter as multimodal_adapter
import backend.app.ocr_adapter as ocr_adapter
import backend.app.vector_store as vector_store
import backend.app.data_store as data_store
from backend.app.main import app


TEN_MB = 10 * 1024 * 1024


def small_pdf_fixture_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 2/Kids[3 0 R 4 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"4 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    return TestClient(app)


def test_health(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"


def test_provider_status_reports_offline_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("MULTIMODAL_PROVIDER", "anthropic")
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["remoteApiMode"] == "off"
    assert payload["offlineFallback"] is True
    assert payload["llm"]["provider"] == "openai"
    assert payload["llm"]["effectiveProvider"] == "mock"
    assert payload["multimodal"]["provider"] == "anthropic"
    assert payload["multimodal"]["effectiveProvider"] == "mock"
    assert payload["ocr"]["provider"] == "mock"
    assert payload["ocr"]["effectiveProvider"] == "mock"
    assert payload["embedding"]["provider"] == "openai"
    assert payload["embedding"]["effectiveProvider"] == "hash"


def test_provider_status_defaults_to_sqlite_vector_store_with_hash_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("REMOTE_API_MODE", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("RAG_VECTOR_SQLITE_ENGINE", raising=False)
    monkeypatch.delenv("RAG_VECTOR_ENHANCER", raising=False)
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    embedding = response.json()["data"]["embedding"]
    assert embedding["provider"] == "openai"
    assert embedding["vectorStore"] == "sqlite"
    assert embedding["sqliteEngine"]["effective"] == "python_scan"
    assert embedding["vectorEnhancer"]["requested"] == "off"
    assert embedding["remoteCapable"] is True
    assert embedding["keyConfigured"] is False
    assert embedding["effectiveProvider"] == "hash"
    assert embedding["model"] == "text-embedding-3-small"


def test_provider_status_reports_reranker_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "heuristic")
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    reranker = response.json()["data"]["reranker"]
    assert reranker["provider"] == "heuristic"
    assert reranker["supported"] is True
    assert reranker["enabled"] is True
    assert reranker["localCapable"] is True
    assert reranker["effectiveProvider"] == "heuristic"


def test_provider_status_includes_system_observability(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MINERU_ENABLED", "false")
    client = make_client(tmp_path, monkeypatch)
    data_store.save_documents(
        [
            {
                "id": "kdoc-status-001",
                "fileName": "status-manual.pdf",
                "fileType": "application/pdf",
                "suffix": "pdf",
                "sourceName": "状态测试手册",
                "status": "pending_review",
                "chunkCount": 2,
                "pendingReviewCount": 1,
                "parser": "mineru",
                "parserFallback": True,
                "parserFallbackReason": "test fallback",
                "uploadedAt": "2026-06-20T01:00:00Z",
                "url": "/knowledge/files/kdoc-status-001.pdf",
            }
        ]
    )
    data_store.save_document_chunks(
        [
            {
                "id": "kdoc-status-001-chunk-001",
                "documentId": "kdoc-status-001",
                "content": "approved content",
                "snippet": "approved content",
                "review_status": "approved",
                "updated_at": "2026-06-20T02:00:00Z",
            },
            {
                "id": "kdoc-status-001-chunk-002",
                "documentId": "kdoc-status-001",
                "content": "pending content",
                "snippet": "pending content",
                "review_status": "pending_review",
                "updated_at": "2026-06-20T03:00:00Z",
            },
        ]
    )
    data_store.save_knowledge_revisions(
        [
            {
                "id": "krev-status-001",
                "documentId": "kdoc-status-001",
                "chunkId": "kdoc-status-001-chunk-001",
                "createdAt": "2026-06-20T04:00:00Z",
            }
        ]
    )

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    system = response.json()["data"]["system"]
    assert system["knowledge"]["documentCount"] == 1
    assert system["knowledge"]["chunkCount"] == 2
    assert system["knowledge"]["approvedChunkCount"] == 1
    assert system["knowledge"]["chunkStatusCounts"]["pending_review"] == 1
    assert system["knowledge"]["revisionCount"] == 1
    assert system["parsing"]["mineru"]["enabled"] is False
    assert system["parsing"]["latestTask"]["documentId"] == "kdoc-status-001"
    assert system["parsing"]["parserFallbackCount"] == 1
    assert "status" in system["indexing"]["chroma"]
    assert system["indexing"]["latestIndexTime"] is None
    assert system["indexing"]["latestKnownIndexActivityAt"] == "2026-06-20T02:00:00Z"
    assert system["indexing"]["unavailableReason"]


def test_provider_status_keeps_local_multimodal_available_when_offline(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("MULTIMODAL_PROVIDER", "local")
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["offlineFallback"] is True
    assert payload["multimodal"]["provider"] == "local"
    assert payload["multimodal"]["localCapable"] is True
    assert payload["multimodal"]["effectiveProvider"] == "local"


def test_local_multimodal_validate_runs_even_when_remote_mode_off(tmp_path, monkeypatch) -> None:
    def fake_real_multimodal(*_: Any, **__: Any) -> dict[str, Any]:
        return {"summary": "本地视觉模型验收通过。"}

    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("MULTIMODAL_PROVIDER", "local")
    monkeypatch.setattr(multimodal_adapter, "real_multimodal_analysis", fake_real_multimodal)
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/providers/multimodal/validate", json={"provider": "local"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "local"
    assert data["remoteOk"] is True
    assert data["fallback"] is False
    assert "本地视觉模型" in data["summaryPreview"]


def test_local_multimodal_uses_openai_compatible_vision_payload(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "本地模型识别到设备故障图片。"}}]}

    image = tmp_path / "fault.png"
    image.write_bytes(b"image-bytes")
    monkeypatch.setenv("LOCAL_MULTIMODAL_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCAL_MULTIMODAL_MODEL", "llava:latest")
    monkeypatch.setattr(multimodal_adapter, "_post_json", fake_post_json)

    result = multimodal_adapter.real_multimodal_analysis(image, "fault.png", "png", "local")

    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["payload"]["model"] == "llava:latest"
    content = captured["payload"]["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result["provider"] == "local"
    assert result["fallback"] is False
    assert "本地模型" in result["summary"]


def test_search_returns_seed_results(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/search",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "inputType": "text",
            "topK": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["results"]
    first_result = payload["data"]["results"][0]
    assert "字段权重" in payload["data"]["summary"]
    assert first_result["matchedTerms"]
    assert first_result["scoreBreakdown"]["score"] > 0
    assert first_result["scoreBreakdown"]["fieldMatches"]


def test_search_rejects_empty_query(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/search",
        json={
            "deviceModel": "  ",
            "faultText": "",
            "inputType": "text",
            "topK": 5,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert "不能同时为空" in payload["message"]


def test_rag_answer_returns_mock_response_with_citations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "topK": 3,
            "provider": "mock",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["provider"] == "mock"
    assert payload["data"]["fallback"] is True
    assert payload["data"]["citations"]
    assert payload["data"]["citations"][0]["scoreBreakdown"]["score"] > 0
    assert "【初步判断】" in payload["data"]["answer"]
    assert "【引用证据】" in payload["data"]["answer"]
    assert payload["data"]["evidencePack"]["evidenceCount"] == len(payload["data"]["citations"])
    assert payload["data"]["structuredAnswer"]["citations"]
    assert payload["data"]["structuredAnswer"]["uncertainInformation"]
    assert payload["data"]["correctiveRag"]["enabled"] is True
    assert payload["data"]["correctiveRag"]["action"] in {"answer", "answer_with_caution", "needs_more_evidence"}
    assert payload["data"]["safetyRules"]["enabled"] is True
    assert "findings" in payload["data"]["safetyRules"]


def test_diagnosis_reuses_search_and_rag_citations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/diagnosis",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "evidenceIds": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["possibleCauses"]
    assert payload["recommendedActions"]
    assert payload["safetyNotes"]
    assert payload["citations"]
    assert payload["provider"] == "mock"
    assert "queryId" in payload


def test_rag_answer_openai_provider_falls_back_to_mock(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "mock"
    assert payload["requestedProvider"] == "openai"
    assert payload["fallback"] is True


def test_rag_answer_remote_api_mode_off_skips_real_provider(tmp_path, monkeypatch) -> None:
    def fail_if_called(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("real provider should not be called while REMOTE_API_MODE=off")

    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(llm_adapter, "real_rag_answer", fail_if_called)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "mock"
    assert payload["requestedProvider"] == "openai"
    assert payload["fallback"] is True
    assert "REMOTE_API_MODE=off" in payload["fallbackReason"]


def test_rag_answer_uses_openai_provider_when_configured(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "https://example-openai.test/v1/responses"
        assert headers["Authorization"] == "Bearer test-openai-key"
        assert payload["model"] == "test-openai-model"
        assert "启动困难" in payload["input"]
        assert timeout == 7
        return {"output_text": "这是 OpenAI provider 返回的检修建议。"}

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example-openai.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "test-openai-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "responses")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "openai"
    assert payload["fallback"] is False
    assert payload["rawAnswer"] == "这是 OpenAI provider 返回的检修建议。"
    assert "【初步判断】" in payload["answer"]


def test_rag_answer_uses_structured_real_llm_answer_when_compliant(tmp_path, monkeypatch) -> None:
    structured_answer = (
        "【初步判断】\n基于 [1]，优先怀疑点火或供油异常。\n\n"
        "【检修等级说明】\n一般检修场景，需按标准工序确认风险边界。\n\n"
        "【作业前准备】\n1. 准备工单、工具和安全隔离措施。\n\n"
        "【建议检查步骤】\n1. 对照 [1] 检查火花塞和供油状态。\n\n"
        "【建议维修步骤】\n1. 仅在 [1] 支持时清洁或更换相关部件。\n\n"
        "【作业中风险控制】\n1. 记录关键操作，异常时停止作业并复核。\n\n"
        "【合规校验提醒】\n1. 检查记录、复测记录和引用证据必须完整。\n\n"
        "【安全提醒】\n1. 作业前断电并等待高温部件冷却。\n\n"
        "【验收标准】\n1. 复测启动状态并记录结果。\n\n"
        "【引用证据】\n[1]\n\n"
        "【不确定信息】\n1. 未在证据中出现的参数不做推断。"
    )

    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert "【建议检查步骤】" in payload["messages"][0]["content"]
        assert "【合规校验提醒】" in payload["messages"][0]["content"]
        assert "不得编造参数" in payload["messages"][0]["content"]
        return {"choices": [{"message": {"content": structured_answer}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["fallback"] is False
    assert payload["rawAnswer"] == structured_answer
    assert payload["answer"] != payload["rawAnswer"]
    assert "【初步判断】" in payload["answer"]
    assert payload["llmAnswerUsed"] is True
    assert payload["llmAnswerMode"] == "structured_evidence_answer"
    assert "llmAnswerPreservedAfterRules" not in payload


def test_rag_answer_uses_openai_compatible_chat_completions(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "https://compatible-provider.test/v1/chat/completions"
        assert headers["Authorization"] == "Bearer compatible-key"
        assert payload["model"] == "compatible-model"
        assert payload["max_tokens"] == 256
        assert payload["temperature"] == 0.1
        assert payload["messages"][0]["role"] == "user"
        assert "启动困难" in payload["messages"][0]["content"]
        return {"choices": [{"message": {"content": "这是兼容 OpenAI Chat Completions 的模型返回。"}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.1")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "openai"
    assert payload["fallback"] is False
    assert payload["rawAnswer"] == "这是兼容 OpenAI Chat Completions 的模型返回。"
    assert "【建议检查步骤】" in payload["answer"]
    assert payload["model"] == "compatible-model"
    assert payload["apiStyle"] == "chat_completions"
    assert payload["contextCount"] > 0


def test_rag_answer_sends_chroma_context_to_real_llm(tmp_path, monkeypatch) -> None:
    def fake_vector_search(_: str, __: int) -> list[dict[str, Any]]:
        return [
            {
                "id": "kdoc-vector-chunk-001",
                "title": "链条润滑检查",
                "sourceType": "document",
                "sourceName": "Chroma 检修资料",
                "snippet": "链条润滑不足会导致运行噪声升高，应检查张紧度和润滑状态。",
                "documentId": "kdoc-vector",
                "chunkId": "kdoc-vector-chunk-001",
                "page": None,
                "distance": 0.1,
            }
        ]

    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        prompt = payload["messages"][0]["content"]
        assert url == "https://compatible-provider.test/v1/chat/completions"
        assert "Chroma 检修资料" in prompt
        assert "链条润滑不足" in prompt
        assert "[1]" in prompt
        return {"choices": [{"message": {"content": "应根据 Chroma 资料检查链条润滑与张紧度。[1]"}}]}

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setattr(vector_store, "search_similar_chunks", fake_vector_search)
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "摩托车",
            "faultText": "异响",
            "topK": 5,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "openai"
    assert payload["fallback"] is False
    assert any(item["sourceName"] == "Chroma 检修资料" for item in payload["citations"])


def test_llm_validate_openai_compatible_success(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "https://compatible-provider.test/v1/chat/completions"
        assert payload["max_tokens"] == 256
        assert payload["temperature"] == 0.1
        return {"choices": [{"message": {"content": "真实 API 验收回答。"}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.1")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/providers/llm/validate",
        json={"deviceModel": "发动机-示例型号 A", "faultText": "启动困难", "topK": 2, "provider": "openai"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["remoteOk"] is True
    assert payload["provider"] == "openai"
    assert payload["model"] == "compatible-model"
    assert payload["apiStyle"] == "chat_completions"
    assert payload["answerPreview"]


def test_llm_validate_remote_api_mode_off_skips_real_provider(tmp_path, monkeypatch) -> None:
    def fail_if_called(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("real provider should not be called while REMOTE_API_MODE=off")

    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setattr(llm_adapter, "_post_json", fail_if_called)
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/providers/llm/validate", json={"provider": "openai"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["remoteOk"] is False
    assert payload["fallback"] is True
    assert "REMOTE_API_MODE=off" in payload["fallbackReason"]


def test_rag_answer_network_error_falls_back_to_mock(tmp_path, monkeypatch) -> None:
    def fail_post_json(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("simulated timeout")

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(llm_adapter, "_post_json", fail_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "mock"
    assert payload["requestedProvider"] == "openai"
    assert payload["fallback"] is True


def test_rag_answer_uses_anthropic_provider_when_configured(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "https://example-anthropic.test/v1/messages"
        assert headers["x-api-key"] == "test-anthropic-key"
        assert payload["model"] == "test-anthropic-model"
        assert payload["messages"][0]["role"] == "user"
        return {"content": [{"type": "text", "text": "这是 Anthropic provider 返回的检修建议。"}]}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example-anthropic.test/v1")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-anthropic-model")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "anthropic",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "anthropic"
    assert payload["fallback"] is False
    assert payload["rawAnswer"] == "这是 Anthropic provider 返回的检修建议。"
    assert "【安全提醒】" in payload["answer"]


def test_rag_answer_uses_environment_provider_when_request_omits_provider(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {"output_text": "环境变量 provider 生效。"}

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_API_STYLE", "responses")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={"deviceModel": "发动机-示例型号 A", "faultText": "启动困难", "topK": 2},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "openai"
    assert payload["fallback"] is False
    assert payload["rawAnswer"] == "环境变量 provider 生效。"
    assert "【验收标准】" in payload["answer"]


def test_rag_answer_rejects_empty_query(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={"deviceModel": " ", "faultText": "", "topK": 3, "provider": "mock"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "不能同时为空" in payload["message"]


def test_workflow_lookup(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/api/workflows/wf-001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["id"] == "wf-001"


def test_expanded_seed_workflows_are_searchable(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    scenarios = [
        ("发动机-示例型号 D", "机油压力低 润滑不足 高温报警", "wf-004"),
        ("电气系统-示例型号 E", "无法上电 保险丝 主继电器", "wf-005"),
        ("传动系统-示例型号 F", "链条张紧 传动异响 润滑", "wf-006"),
    ]

    for device_model, fault_text, workflow_id in scenarios:
        search_response = client.post(
            "/api/search",
            json={"deviceModel": device_model, "faultText": fault_text, "inputType": "text", "topK": 5},
        )

        assert search_response.status_code == 200
        results = search_response.json()["data"]["results"]
        assert any(item.get("workflowId") == workflow_id for item in results)

        workflow_response = client.get(f"/api/workflows/{workflow_id}")
        assert workflow_response.status_code == 200
        workflow = workflow_response.json()["data"]
        assert workflow["id"] == workflow_id
        assert len(workflow["steps"]) >= 3
        assert workflow["tools"]
        assert workflow["safetyNotes"]


def test_global_graph_includes_expanded_seed_workflows(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/knowledge/graph/rebuild")

    assert response.status_code == 200
    graph = response.json()["data"]
    labels = {node["label"] for node in graph["nodes"]}
    assert any("润滑" in label for label in labels)
    assert any("电气" in label or "上电" in label for label in labels)
    assert any("链传动" in label or "链条" in label for label in labels)
    assert graph["stats"]["nodeTypes"]["workflow"] >= 6


def test_upload_uses_configured_upload_dir(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("APP_UPLOAD_DIR", str(upload_dir))

    response = client.post(
        "/api/uploads",
        files={"file": ("fault-image.jpg", b"fake image bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["fileName"] == "fault-image.jpg"
    assert (upload_dir / f"{payload['data']['id']}.jpg").exists()


def test_upload_accepts_allowed_file_types(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("APP_UPLOAD_DIR", str(upload_dir))
    allowed_files = [
        ("fault-image.jpg", b"jpg bytes", "image/jpeg", ".jpg"),
        ("fault-image.png", b"png bytes", "image/png", ".png"),
        ("fault-image.webp", b"webp bytes", "image/webp", ".webp"),
        ("manual.pdf", b"%PDF-1.4 bytes", "application/pdf", ".pdf"),
    ]

    for file_name, content, content_type, suffix in allowed_files:
        response = client.post("/api/uploads", files={"file": (file_name, content, content_type)})

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert (upload_dir / f"{payload['data']['id']}{suffix}").exists()


def test_upload_rejects_empty_file(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_UPLOAD_DIR", str(tmp_path / "uploads"))

    response = client.post(
        "/api/uploads",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert "不能为空" in payload["message"]


def test_upload_rejects_unsupported_extension(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_UPLOAD_DIR", str(tmp_path / "uploads"))

    response = client.post(
        "/api/uploads",
        files={"file": ("script.exe", b"binary", "application/octet-stream")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "仅支持" in payload["message"]


def test_upload_rejects_mime_mismatch(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_UPLOAD_DIR", str(tmp_path / "uploads"))

    response = client.post(
        "/api/uploads",
        files={"file": ("fault-image.jpg", b"not really pdf", "application/pdf")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "MIME" in payload["message"]


def test_upload_rejects_oversized_file(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("APP_UPLOAD_DIR", str(tmp_path / "uploads"))

    response = client.post(
        "/api/uploads",
        files={"file": ("too-large.pdf", b"x" * (TEN_MB + 1), "application/pdf")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "10MB" in payload["message"]


def test_case_submit_review_and_search_round_trip(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    create_response = client.post(
        "/api/cases",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "热机后偶发熄火，怠速控制异常",
            "cause": "怠速控制阀积碳",
            "solution": "清洁怠速控制阀并复测怠速稳定性",
            "result": "热机后未再熄火",
            "tags": ["偶发熄火", "怠速控制"],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["status"] == "pending_review"

    pending_response = client.get("/api/cases?status=pending_review")
    pending_items = pending_response.json()["data"]["items"]
    assert any(item["id"] == created["id"] for item in pending_items)

    review_response = client.patch(
        f"/api/cases/{created['id']}/review",
        json={
            "action": "approve",
            "reviewNote": "内容完整，可入库",
            "normalizedTags": ["偶发熄火", "怠速控制", "发动机"],
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "approved"

    search_response = client.post(
        "/api/search",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "偶发熄火 怠速控制",
            "inputType": "text",
            "topK": 5,
        },
    )
    results = search_response.json()["data"]["results"]
    assert any(item["id"] == created["id"] and item["sourceType"] == "case" for item in results)

    cases_file = tmp_path / "source" / "repair-cases.json"
    saved_cases = json.loads(cases_file.read_text(encoding="utf-8"))
    saved_case = next(item for item in saved_cases if item["id"] == created["id"])
    assert saved_case["status"] == "approved"
    assert saved_case["reviewedAt"]
    events = data_store.load_review_events()
    assert events[-1]["objectType"] == "case"
    assert events[-1]["before"]["status"] == "pending_review"
    assert events[-1]["after"]["status"] == "approved"
    assert events[-1]["after"]["tags"] == ["偶发熄火", "怠速控制", "发动机"]


def test_case_create_preserves_metadata_and_workflow_selection(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/cases",
        json={
            "deviceType": "传动系统",
            "deviceModel": "CHAIN-DRIVE-A",
            "faultText": "传动异响",
            "cause": "链条张紧度异常",
            "solution": "调整张紧度并补充润滑",
            "result": "异响降低",
            "riskLevel": "high",
            "maintenanceLevel": "focused_repair",
            "workflowId": "wf-006",
            "tags": ["链条", "异响"],
        },
    )

    assert response.status_code == 200
    created = response.json()["data"]
    assert created["deviceType"] == "传动系统"
    assert created["riskLevel"] == "high"
    assert created["maintenanceLevel"] == "focused_repair"
    assert created["workflowId"] == "wf-006"


def create_pending_case(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/cases",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "review pending fixture",
            "cause": "pending cause",
            "solution": "pending solution",
            "result": "pending result",
            "tags": ["pending"],
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_invalid_review_action_is_rejected_without_status_change(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    pending_case = create_pending_case(client)

    response = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        json={"action": "archive", "reviewNote": "非法动作"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None

    after_response = client.get("/api/cases?status=pending_review")
    after_items = after_response.json()["data"]["items"]
    assert any(item["id"] == pending_case["id"] for item in after_items)


def test_case_review_reject_requires_reason(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    pending_case = create_pending_case(client)

    response = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        json={"action": "reject", "reviewNote": ""},
    )

    assert response.status_code == 400
    after_items = client.get("/api/cases?status=pending_review").json()["data"]["items"]
    assert any(item["id"] == pending_case["id"] for item in after_items)


def test_review_events_api_filters_audit_log(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    pending_case = create_pending_case(client)
    review_response = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        json={"action": "approve", "reviewNote": "审计流水测试", "reviewer": "auditor"},
    )
    assert review_response.status_code == 200

    response = client.get(
        f"/api/review/events?object_type=case&object_id={pending_case['id']}&action=approve&limit=1"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["limit"] == 1
    assert data["items"][0]["objectType"] == "case"
    assert data["items"][0]["objectId"] == pending_case["id"]
    assert data["items"][0]["reviewer"] == "auditor"
    assert data["items"][0]["before"]["status"] == "pending_review"
    assert data["items"][0]["after"]["status"] == "approved"


def test_token_auth_protects_review_and_admin_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("AUTH_OPERATOR_TOKEN", "operator-token")
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", "review-token")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "admin-token")
    client = make_client(tmp_path, monkeypatch)
    pending_case = create_pending_case(client)

    missing = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        json={"action": "approve", "reviewNote": "needs auth"},
    )
    assert missing.status_code == 401

    invalid = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        headers={"Authorization": "Bearer wrong-token"},
        json={"action": "approve", "reviewNote": "bad token"},
    )
    assert invalid.status_code == 401

    malformed = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        headers={"Authorization": "Token review-token"},
        json={"action": "approve", "reviewNote": "bad bearer"},
    )
    assert malformed.status_code == 401

    operator = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        headers={"Authorization": "Bearer operator-token"},
        json={"action": "approve", "reviewNote": "operator blocked"},
    )
    assert operator.status_code == 403

    reviewer = client.patch(
        f"/api/cases/{pending_case['id']}/review",
        headers={"Authorization": "Bearer review-token"},
        json={"action": "approve", "reviewNote": "reviewer ok"},
    )
    assert reviewer.status_code == 200

    admin_only = client.post(
        "/api/knowledge/graph/rebuild",
        headers={"Authorization": "Bearer review-token"},
    )
    assert admin_only.status_code == 403

    admin = client.post(
        "/api/knowledge/graph/rebuild",
        headers={"Authorization": "Bearer admin-token"},
    )
    assert admin.status_code == 200


def test_token_auth_role_matrix_and_status_visibility(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("AUTH_OPERATOR_TOKEN", "operator-token")
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", "review-token")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "admin-token")
    client = make_client(tmp_path, monkeypatch)
    pending_case = create_pending_case(client)
    save_pending_review_chunk()

    # Public read and submission paths remain available by design.
    assert client.post("/api/search", json={"faultText": "review pending fixture"}).status_code == 200
    assert client.post(
        "/api/rag/answer",
        json={"deviceModel": "engine", "faultText": "review pending fixture", "provider": "mock"},
    ).status_code == 200
    assert create_pending_case(client)["status"] == "pending_review"

    matrix = [
        ("case reviewer denied anonymous", "PATCH", f"/api/cases/{pending_case['id']}/review", None, 401),
        ("case reviewer denied operator", "PATCH", f"/api/cases/{pending_case['id']}/review", "operator-token", 403),
        ("case reviewer allowed reviewer", "PATCH", f"/api/cases/{pending_case['id']}/review", "review-token", 200),
        (
            "chunk review denied operator",
            "PATCH",
            "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/review",
            "operator-token",
            403,
        ),
        (
            "chunk review allowed reviewer",
            "PATCH",
            "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/review",
            "review-token",
            200,
        ),
        (
            "status update denied reviewer",
            "PATCH",
            "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/status",
            "review-token",
            403,
        ),
        (
            "status update allowed admin",
            "PATCH",
            "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/status",
            "admin-token",
            200,
        ),
        ("graph rebuild denied reviewer", "POST", "/api/knowledge/graph/rebuild", "review-token", 403),
        ("graph rebuild allowed admin", "POST", "/api/knowledge/graph/rebuild", "admin-token", 200),
        ("delete denied reviewer", "DELETE", "/api/knowledge/documents/kdoc-review-001", "review-token", 403),
        ("delete allowed admin", "DELETE", "/api/knowledge/documents/kdoc-review-001", "admin-token", 200),
    ]
    for _label, method, path, token, expected_status in matrix:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        json_body = {"action": "approve", "reviewNote": "ok", "reason": "ok", "status": "approved"}
        response = client.request(method, path, headers=headers, json=json_body)
        assert response.status_code == expected_status

    status = client.get("/api/providers/status").json()["data"]
    auth = status["system"]["auth"]
    assert auth == {
        "mode": "token",
        "enabled": True,
        "operatorConfigured": True,
        "reviewerConfigured": True,
        "adminConfigured": True,
    }
    assert "operator-token" not in str(status)
    assert "review-token" not in str(status)
    assert "admin-token" not in str(status)


def test_auth_mode_off_is_explicit_in_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    client = make_client(tmp_path, monkeypatch)

    status = client.get("/api/providers/status").json()["data"]

    assert status["system"]["auth"]["mode"] == "off"
    assert status["system"]["auth"]["enabled"] is False
    assert any("AUTH_MODE=off" in item for item in status["system"]["warnings"])


def test_knowledge_directory_is_not_public_static_mount(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    assert client.get("/knowledge/files/kdoc-review-001.pdf").status_code == 404
    assert client.get("/knowledge/../examples/repair-cases.json").status_code == 404
    assert client.get("/knowledge/%2E%2E/examples/repair-cases.json").status_code == 404


def save_pending_review_chunk() -> None:
    data_store.save_documents(
        [
            {
                "id": "kdoc-review-001",
                "fileName": "review-manual.pdf",
                "fileType": "application/pdf",
                "suffix": "pdf",
                "sourceName": "审核测试资料",
                "status": "pending_review",
                "chunkCount": 1,
                "pendingReviewCount": 1,
                "parser": "mock-parser",
                "parserFallback": True,
                "parserFallbackReason": "test",
                "uploadedAt": "2026-06-21T01:00:00Z",
                "url": "/knowledge/files/kdoc-review-001.pdf",
            }
        ]
    )
    data_store.save_document_chunks(
        [
            {
                "id": "kdoc-review-001-chunk-001",
                "chunk_id": "kdoc-review-001-chunk-001",
                "documentId": "kdoc-review-001",
                "source_doc_id": "kdoc-review-001",
                "title": "审核测试片段",
                "sourceType": "document",
                "sourceName": "审核测试资料",
                "content": "待审核检修片段，包含断电和验收步骤。",
                "snippet": "待审核检修片段，包含断电和验收步骤。",
                "keywords": ["断电", "验收"],
                "review_status": "pending_review",
                "created_at": "2026-06-21T01:00:00Z",
                "updated_at": "2026-06-21T01:00:00Z",
            }
        ]
    )


def save_approved_lifecycle_chunks() -> None:
    data_store.save_documents(
        [
            {
                "id": "kdoc-life-001",
                "fileName": "lifecycle-manual.md",
                "fileType": "text/markdown",
                "suffix": "md",
                "sourceName": "生命周期测试资料",
                "status": "indexed",
                "chunkCount": 2,
                "pendingReviewCount": 0,
                "parser": "plain-text",
                "parserFallback": False,
                "parserFallbackReason": "",
                "uploadedAt": "2026-06-22T01:00:00Z",
                "url": "/knowledge/files/kdoc-life-001.md",
            }
        ]
    )
    data_store.save_document_chunks(
        [
            {
                "id": "kdoc-life-001-chunk-001",
                "chunk_id": "kdoc-life-001-chunk-001",
                "documentId": "kdoc-life-001",
                "source_doc_id": "kdoc-life-001",
                "title": "生命周期原始片段",
                "sourceType": "document",
                "sourceName": "生命周期测试资料",
                "content": "生命周期专用检索词 alpha beta gamma。",
                "snippet": "生命周期专用检索词 alpha beta gamma。",
                "keywords": ["生命周期", "alpha", "beta", "gamma"],
                "review_status": "approved",
                "created_at": "2026-06-22T01:00:00Z",
                "updated_at": "2026-06-22T01:00:00Z",
            },
            {
                "id": "kdoc-life-001-chunk-002",
                "chunk_id": "kdoc-life-001-chunk-002",
                "documentId": "kdoc-life-001",
                "source_doc_id": "kdoc-life-001",
                "title": "生命周期替换片段",
                "sourceType": "document",
                "sourceName": "生命周期测试资料",
                "content": "替换后的生命周期专用检索词 delta epsilon。",
                "snippet": "替换后的生命周期专用检索词 delta epsilon。",
                "keywords": ["生命周期", "delta", "epsilon"],
                "review_status": "approved",
                "created_at": "2026-06-22T01:00:00Z",
                "updated_at": "2026-06-22T01:00:00Z",
            },
        ]
    )


def test_review_items_include_pending_cases_and_knowledge_chunks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_pending_case(client)
    save_pending_review_chunk()

    response = client.get("/api/review/items?status=pending_review")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert any(item["objectType"] == "case" for item in items)
    chunk_item = next(item for item in items if item["objectType"] == "knowledge_chunk")
    assert chunk_item["documentId"] == "kdoc-review-001"
    assert chunk_item["chunkId"] == "kdoc-review-001-chunk-001"
    assert chunk_item["status"] == "pending_review"


def test_knowledge_chunk_review_reject_requires_reason(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    save_pending_review_chunk()

    response = client.patch(
        "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/review",
        json={"action": "reject", "reason": "", "reviewer": "qa"},
    )

    assert response.status_code == 400
    chunks = data_store.load_document_chunks()
    assert chunks[0]["review_status"] == "pending_review"


def test_knowledge_chunk_review_approve_records_event_and_syncs_chroma(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    save_pending_review_chunk()
    deleted: list[str] = []
    sync_calls: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: deleted.append(document_id))
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: sync_calls.append(chunks))

    response = client.patch(
        "/api/knowledge/documents/kdoc-review-001/chunks/kdoc-review-001-chunk-001/review",
        json={"action": "approve", "reason": "来源可信", "reviewer": "qa"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["chunk"]["review_status"] == "approved"
    assert data["chunk"]["reviewer"] == "qa"
    assert data["chunk"]["review_action"] == "approve"
    assert data["document"]["status"] == "indexed"
    assert data["reviewEvent"]["action"] == "approve"
    assert data["reviewEvent"]["reviewer"] == "qa"
    assert deleted == ["kdoc-review-001"]
    assert sync_calls and sync_calls[-1][0]["review_status"] == "approved"
    events = data_store.load_review_events()
    assert events[-1]["objectType"] == "knowledge_chunk"
    assert events[-1]["afterStatus"] == "approved"
    assert events[-1]["before"]["review_status"] == "pending_review"
    assert events[-1]["after"]["review_status"] == "approved"


def test_knowledge_chunk_status_deprecate_removes_from_retrieval(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    save_approved_lifecycle_chunks()
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)

    before = client.post(
        "/api/search",
        json={"deviceModel": "", "faultText": "alpha beta gamma", "inputType": "text", "topK": 5},
    )
    assert any(item.get("chunkId") == "kdoc-life-001-chunk-001" for item in before.json()["data"]["results"])

    response = client.patch(
        "/api/knowledge/documents/kdoc-life-001/chunks/kdoc-life-001-chunk-001/status",
        json={"status": "deprecated", "reason": "内容过期", "reviewer": "qa"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["chunk"]["review_status"] == "deprecated"
    assert data["reviewEvent"]["action"] == "set_deprecated"
    after = client.post(
        "/api/search",
        json={"deviceModel": "", "faultText": "alpha beta gamma", "inputType": "text", "topK": 5},
    )
    assert not any(item.get("chunkId") == "kdoc-life-001-chunk-001" for item in after.json()["data"]["results"])


def test_knowledge_chunk_status_replaced_requires_replacement_chunk(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    save_approved_lifecycle_chunks()

    missing = client.patch(
        "/api/knowledge/documents/kdoc-life-001/chunks/kdoc-life-001-chunk-001/status",
        json={"status": "replaced", "reason": "使用新片段", "reviewer": "qa"},
    )
    assert missing.status_code == 400

    response = client.patch(
        "/api/knowledge/documents/kdoc-life-001/chunks/kdoc-life-001-chunk-001/status",
        json={
            "status": "replaced",
            "reason": "使用新片段",
            "reviewer": "qa",
            "replacementChunkId": "kdoc-life-001-chunk-002",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["chunk"]["review_status"] == "replaced"
    assert data["chunk"]["replaced_by"] == "kdoc-life-001-chunk-002"
    assert data["reviewEvent"]["replacementChunkId"] == "kdoc-life-001-chunk-002"


def test_knowledge_document_upload_creates_pending_review_chunks_and_parse_artifacts(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "motorcycle-manual.md",
                "摩托车发动机无法启动时，应检查火花塞、高压包和燃油供给。".encode("utf-8"),
                "text/markdown",
            )
        },
        data={"source_name": "摩托车检修手册"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "pending_review"
    assert payload["data"]["chunkCount"] == 1
    assert payload["data"]["pendingReviewCount"] == 1
    assert payload["data"]["chunks"][0]["review_status"] == "pending_review"
    assert payload["data"]["chunks"][0]["chunk_id"] == payload["data"]["chunks"][0]["id"]
    assert payload["data"]["parseArtifacts"]["rawParseResult"]
    assert payload["data"]["parseArtifacts"]["parsedMarkdown"]
    assert (tmp_path / "knowledge" / "parsed" / payload["data"]["id"] / "raw_parse_result.json").exists()
    assert (tmp_path / "knowledge" / "parsed" / payload["data"]["id"] / "parsed.md").exists()

    search_response = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞",
            "inputType": "text",
            "topK": 5,
        },
    )
    results = search_response.json()["data"]["results"]
    assert not any(item["sourceType"] == "document" and item["sourceName"] == "摩托车检修手册" for item in results)


def test_knowledge_document_upload_auto_analyzes_mineru_assets(tmp_path, monkeypatch) -> None:
    asset_path = tmp_path / "mineru-asset.png"
    asset_path.write_bytes(b"fake image bytes")

    def fake_parse_document(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "parser": "mineru",
            "status": "parsed",
            "pages": [{"page": 1, "section": "manual-page", "text": "手册文本：启动困难检查火花塞。"}],
            "markdown": "# 手册文本",
            "assets": [str(asset_path)],
            "fallback": False,
            "fallbackReason": "",
        }

    def fake_ocr(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "provider": "rapidocr",
            "requestedProvider": "rapidocr",
            "fallback": False,
            "fallbackReason": "",
            "text": "图中标注火花塞间隙检查",
            "textSegments": ["图中标注火花塞间隙检查"],
        }

    def fake_multimodal(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "provider": "openai",
            "requestedProvider": "openai",
            "fallback": False,
            "fallbackReason": "",
            "summary": "图片显示火花塞检查位置。",
            "textSegments": ["图片显示火花塞检查位置，应结合手册文字复核。"],
        }

    monkeypatch.setattr(knowledge, "parse_document", fake_parse_document)
    monkeypatch.setattr(knowledge, "analyze_ocr_document", fake_ocr)
    monkeypatch.setattr(knowledge, "analyze_multimodal_document", fake_multimodal)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"source_name": "图文维修手册"},
    )

    assert response.status_code == 200
    uploaded = response.json()["data"]
    assert uploaded["assetAnalysisStatus"] == "queued"

    detail = client.get(f"/api/knowledge/documents/{uploaded['id']}").json()["data"]
    assert detail["assetAnalysisStatus"] == "completed"
    assert detail["assetAnalysisCount"] == 2
    assert detail["pendingReviewCount"] == 3

    chunks = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]
    knowledge_types = {chunk["knowledge_type"] for chunk in chunks}
    assert {"manual_excerpt", "ocr_result", "image_analysis"} <= knowledge_types
    asset_chunks = [chunk for chunk in chunks if chunk.get("origin") == "mineru_asset_analysis"]
    assert len(asset_chunks) == 2
    assert {chunk["review_status"] for chunk in asset_chunks} == {"pending_review"}
    assert {chunk["sourceType"] for chunk in asset_chunks} == {"document_asset"}
    assert all(chunk["evidence_location"]["assetName"].endswith(".png") for chunk in asset_chunks)

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "发动机", "faultText": "火花塞间隙 图片", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert not any(item.get("documentId") == uploaded["id"] for item in results)


def test_pdf_visual_asset_fallback_when_mineru_timeout(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PDF_PAGE_VISUAL_ASSET_LIMIT", "2")

    def fake_parse_document(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "parser": "pypdf",
            "status": "parsed",
            "pages": [
                {"page": 1, "section": "page-1", "text": "维修手册目录"},
                {"page": 2, "section": "page-2", "text": "火花塞拆卸图示，检查电极间隙。"},
                {"page": 3, "section": "page-3", "text": "起动电机装配图，安装固定螺栓。"},
            ],
            "markdown": "fallback text",
            "assets": [],
            "fallback": True,
            "fallbackReason": "MinerU unavailable: MinerU timed out after 180 seconds.",
        }

    monkeypatch.setattr(knowledge, "parse_document", fake_parse_document)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("official-demo.pdf", small_pdf_fixture_bytes(), "application/pdf")},
        data={"source_name": "官方演示维修手册"},
    )

    assert response.status_code == 200
    uploaded = response.json()["data"]
    detail = client.get(f"/api/knowledge/documents/{uploaded['id']}").json()["data"]
    chunks = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]

    assert detail["assetAnalysisStatus"] == "fallback_completed"
    assert detail["assetAnalysisCount"] > 0
    assert detail["assetAnalysisFallbackCount"] >= 1
    assert detail["assetAnalysisError"]
    assert detail["assetAnalysisError"] != "no_assets"
    assert any(chunk["knowledge_type"] == "manual_excerpt" for chunk in chunks)
    visual_chunks = [chunk for chunk in chunks if chunk["knowledge_type"] == "pdf_page_visual_asset"]
    assert len(visual_chunks) == 2
    assert {chunk["sourceType"] for chunk in visual_chunks} == {"document_asset"}
    assert {chunk["review_status"] for chunk in visual_chunks} == {"pending_review"}
    assert all(chunk.get("assetFallbackType") == "pdf_page_visual_asset" for chunk in visual_chunks)


def test_pdf_visual_asset_fallback_when_no_assets(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PDF_PAGE_VISUAL_ASSET_LIMIT", "3")

    monkeypatch.setattr(
        knowledge,
        "parse_document",
        lambda *_: {
            "parser": "mineru",
            "status": "parsed",
            "pages": [
                {"page": 1, "section": "page-1", "text": "发动机拆装说明。"},
                {"page": 2, "section": "page-2", "text": "气缸活塞装配图示。"},
            ],
            "markdown": "mineru text without assets",
            "assets": [],
            "fallback": False,
            "fallbackReason": "",
        },
    )
    client = make_client(tmp_path, monkeypatch)

    uploaded = client.post(
        "/api/knowledge/documents",
        files={"file": ("no-assets.pdf", small_pdf_fixture_bytes(), "application/pdf")},
    ).json()["data"]
    detail = client.get(f"/api/knowledge/documents/{uploaded['id']}").json()["data"]
    chunks = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]

    assert detail["assetAnalysisStatus"] == "fallback_completed"
    assert detail["assetAnalysisCount"] >= 1
    assert detail["assetAnalysisFallbackCount"] >= 1
    assert any(chunk["knowledge_type"] == "manual_excerpt" for chunk in chunks)
    assert any(chunk["knowledge_type"] == "pdf_page_visual_asset" for chunk in chunks)
    assert all(
        chunk["review_status"] == "pending_review"
        for chunk in chunks
        if chunk["knowledge_type"] in {"manual_excerpt", "pdf_page_visual_asset"}
    )


def test_mineru_asset_analysis_is_idempotent(tmp_path, monkeypatch) -> None:
    asset_path = tmp_path / "asset-idempotent.png"
    asset_path.write_bytes(b"fake image bytes")

    monkeypatch.setattr(
        knowledge,
        "parse_document",
        lambda *_: {
            "parser": "mineru",
            "status": "parsed",
            "pages": [{"page": 1, "section": "manual-page", "text": "文本片段"}],
            "markdown": "文本片段",
            "assets": [str(asset_path)],
            "fallback": False,
            "fallbackReason": "",
        },
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_ocr_document",
        lambda *_: {"provider": "mock", "fallback": False, "textSegments": ["OCR 一次结果"]},
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_multimodal_document",
        lambda *_, **__: {"provider": "mock", "fallback": False, "textSegments": ["图片一次结果"]},
    )
    client = make_client(tmp_path, monkeypatch)
    uploaded = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.pdf", b"%PDF-1.4 fake", "application/pdf")},
    ).json()["data"]

    first = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]
    first_asset_ids = sorted(chunk["id"] for chunk in first if chunk.get("origin") == "mineru_asset_analysis")

    client.post(f"/api/knowledge/documents/{uploaded['id']}/analyze", json={"provider": "mock"})
    second = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]
    second_asset_ids = sorted(chunk["id"] for chunk in second if chunk.get("origin") == "mineru_asset_analysis")

    assert first_asset_ids == second_asset_ids
    assert len(second) == 3
    assert sum(1 for chunk in second if chunk["knowledge_type"] == "manual_excerpt") == 1


def test_mineru_asset_visual_failure_uses_text_llm_fallback(tmp_path, monkeypatch) -> None:
    asset_path = tmp_path / "asset-llm-fallback.png"
    asset_path.write_bytes(b"fake image bytes")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen-test")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setattr(
        knowledge,
        "parse_document",
        lambda *_: {
            "parser": "mineru",
            "status": "parsed",
            "pages": [],
            "markdown": "",
            "assets": [str(asset_path)],
            "fallback": False,
            "fallbackReason": "",
        },
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_ocr_document",
        lambda *_: {"provider": "rapidocr", "fallback": False, "text": "OCR: 制动泵渗漏", "textSegments": ["OCR: 制动泵渗漏"]},
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_multimodal_document",
        lambda *_, **__: {
            "provider": "mock",
            "requestedProvider": "openai",
            "fallback": True,
            "fallbackReason": "vision unavailable",
            "textSegments": ["mock should not be used"],
        },
    )
    monkeypatch.setattr(
        knowledge,
        "_post_json",
        lambda *_args, **_kwargs: {"choices": [{"message": {"content": "LLM 基于 OCR 判断该图可能与制动泵渗漏检查有关；不确定具体参数。"}}]},
    )
    client = make_client(tmp_path, monkeypatch)

    uploaded = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.pdf", b"%PDF-1.4 fake", "application/pdf")},
    ).json()["data"]
    chunks = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]
    image_chunk = next(chunk for chunk in chunks if chunk["knowledge_type"] == "image_analysis")

    assert "LLM 基于 OCR" in image_chunk["content"]
    assert image_chunk["analysisProvider"] == "openai-text-fallback"
    assert image_chunk["analysisFallbackReason"] == "vision unavailable"


def test_mineru_asset_llm_failure_retains_ocr_chunk(tmp_path, monkeypatch) -> None:
    asset_path = tmp_path / "asset-llm-fail.png"
    asset_path.write_bytes(b"fake image bytes")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        knowledge,
        "parse_document",
        lambda *_: {
            "parser": "mineru",
            "status": "parsed",
            "pages": [],
            "markdown": "",
            "assets": [str(asset_path)],
            "fallback": False,
            "fallbackReason": "",
        },
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_ocr_document",
        lambda *_: {"provider": "rapidocr", "fallback": False, "text": "OCR: 油路堵塞", "textSegments": ["OCR: 油路堵塞"]},
    )
    monkeypatch.setattr(
        knowledge,
        "analyze_multimodal_document",
        lambda *_, **__: {"provider": "mock", "fallback": True, "fallbackReason": "vision unavailable", "textSegments": []},
    )
    monkeypatch.setattr(knowledge, "_post_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("llm down")))
    client = make_client(tmp_path, monkeypatch)

    uploaded = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.pdf", b"%PDF-1.4 fake", "application/pdf")},
    ).json()["data"]
    detail = client.get(f"/api/knowledge/documents/{uploaded['id']}").json()["data"]
    chunks = client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks").json()["data"]["items"]

    assert detail["assetAnalysisStatus"] == "completed"
    assert detail["assetAnalysisFallbackCount"] >= 1
    assert any(chunk["knowledge_type"] == "ocr_result" for chunk in chunks)
    assert not any(chunk["knowledge_type"] == "image_analysis" for chunk in chunks)
    assert "llm down" in detail["assetAnalysisError"]


def test_knowledge_document_upload_does_not_sync_pending_chunks_to_vector_store(tmp_path, monkeypatch) -> None:
    synced: list[dict[str, Any]] = []

    def capture_sync(chunks: list[dict[str, Any]]) -> None:
        synced.extend(chunks)

    monkeypatch.setattr(knowledge, "sync_chunks", capture_sync)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "motorcycle-manual.md",
                "摩托车发动机无法启动时，应检查火花塞、高压包和燃油供给。".encode("utf-8"),
                "text/markdown",
            )
        },
        data={"source_name": "摩托车检修手册"},
    )

    assert response.status_code == 200
    assert synced == []


def test_async_knowledge_document_parse_task_ingests_pending_review_document(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents/async",
        files={
            "file": (
                "async-manual.md",
                "异步解析资料：制动泵渗漏时，应检查密封圈并执行安全泄压。".encode("utf-8"),
                "text/markdown",
            )
        },
        data={"source_name": "异步检修手册"},
    )

    assert response.status_code == 200
    queued_task = response.json()["data"]
    assert queued_task["status"] == "queued"
    assert queued_task["documentId"] is None
    assert "queuedFile" not in queued_task

    task_response = client.get(f"/api/knowledge/parse-tasks/{queued_task['id']}")
    assert task_response.status_code == 200
    task = task_response.json()["data"]
    assert "queuedFile" not in task
    assert task["status"] == "completed"
    assert task["documentId"].startswith("kdoc-")
    assert task["documentStatus"] == "pending_review"
    assert task["chunkCount"] == 1

    document_response = client.get(f"/api/knowledge/documents/{task['documentId']}")
    assert document_response.status_code == 200
    document = document_response.json()["data"]
    assert document["sourceName"] == "异步检修手册"
    assert document["status"] == "pending_review"
    assert document["chunks"][0]["review_status"] == "pending_review"

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "", "faultText": "制动泵渗漏 安全泄压", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert not any(item.get("documentId") == task["documentId"] for item in results)


def test_async_knowledge_parse_task_records_failure(tmp_path, monkeypatch) -> None:
    def fail_ingest(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(knowledge, "ingest_knowledge_document_bytes", fail_ingest)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("broken.md", b"valid queued bytes", "text/markdown")},
        data={"source_name": "失败资料"},
    )

    assert response.status_code == 200
    task_id = response.json()["data"]["id"]

    task_response = client.get(f"/api/knowledge/parse-tasks/{task_id}")
    assert task_response.status_code == 200
    task = task_response.json()["data"]
    assert task["status"] == "failed"
    assert "synthetic parser failure" in task["error"]
    assert task["documentId"] is None


def test_provider_status_reports_async_parse_tasks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("async-status.md", b"async status readiness content", "text/markdown")},
        data={"source_name": "状态资料"},
    )
    task_id = response.json()["data"]["id"]

    status_response = client.get("/api/providers/status")

    assert status_response.status_code == 200
    parsing = status_response.json()["data"]["system"]["parsing"]
    assert parsing["asyncTaskCount"] == 1
    assert parsing["asyncTaskStatusCounts"]["completed"] == 1
    assert parsing["latestAsyncTask"]["taskId"] == task_id
    assert parsing["latestAsyncTask"]["status"] == "completed"


def test_docx_upload_falls_back_to_mock_parser_pending_review(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "maintenance.docx",
                b"fake office bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"source_name": "Office 检修资料"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "needs_parser"
    assert payload["parser"] == "mock-parser"
    assert payload["parserFallback"] is True
    assert "MinerU unavailable" in payload["parserFallbackReason"]
    assert (tmp_path / "knowledge" / "parsed" / payload["id"] / "raw_parse_result.json").exists()


def test_search_merges_chroma_vector_recall(tmp_path, monkeypatch) -> None:
    def fake_vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
        assert "异响" in query
        assert top_k == 20
        return [
            {
                "id": "kdoc-vector-chunk-001",
                "title": "链条润滑检查",
                "sourceType": "document",
                "sourceName": "Chroma 检修资料",
                "snippet": "链条润滑不足会导致运行噪声升高，应检查张紧度和润滑状态。",
                "documentId": "kdoc-vector",
                "chunkId": "kdoc-vector-chunk-001",
                "reviewStatus": "approved",
                "page": None,
                "distance": 0.12,
            }
        ]

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setattr(vector_store, "search_similar_chunks", fake_vector_search)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车",
            "faultText": "异响",
            "inputType": "text",
            "topK": 5,
        },
    )

    assert response.status_code == 200
    results = response.json()["data"]["results"]
    vector_item = next(item for item in results if item["id"] == "kdoc-vector-chunk-001")
    assert vector_item["sourceName"] == "Chroma 检修资料"
    assert "Chroma" in vector_item["reason"]
    assert vector_item["scoreBreakdown"]["vectorDistance"] == 0.12


def test_rag_answer_excludes_pending_review_document_citation(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "motorcycle-manual.md",
                "摩托车发动机无法启动时，应检查火花塞、高压包和燃油供给。".encode("utf-8"),
                "text/markdown",
            )
        },
        data={"source_name": "摩托车检修手册"},
    )

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞",
            "topK": 5,
            "provider": "mock",
        },
    )

    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert not any(item["sourceType"] == "document" and item["sourceName"] == "摩托车检修手册" for item in citations)


def test_knowledge_documents_list_returns_ingested_items(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.txt", b"brake inspection and tire pressure", "text/plain")},
    )

    response = client.get("/api/knowledge/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["fileName"] == "manual.txt"


def test_knowledge_document_detail_and_chunks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "manual.md",
                "第一段：检查制动片厚度。\n第二段：检查轮胎胎压和磨损。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    document_id = upload_response.json()["data"]["id"]

    detail_response = client.get(f"/api/knowledge/documents/{document_id}")
    chunks_response = client.get(f"/api/knowledge/documents/{document_id}/chunks")

    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["id"] == document_id
    assert detail["chunkTotal"] == 1
    assert detail["chunks"][0]["documentId"] == document_id

    assert chunks_response.status_code == 200
    chunks = chunks_response.json()["data"]
    assert chunks["total"] == 1
    assert "制动片" in chunks["items"][0]["content"]


def test_delete_knowledge_document_removes_chunks_and_search_result(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={
            "file": (
                "manual.md",
                "摩托车链条异响时，应检查链条张紧度和润滑状态。".encode("utf-8"),
                "text/markdown",
            )
        },
        data={"source_name": "链条检修资料"},
    )
    document_id = upload_response.json()["data"]["id"]

    delete_response = client.delete(f"/api/knowledge/documents/{document_id}")
    detail_response = client.get(f"/api/knowledge/documents/{document_id}")
    chunks_response = client.get(f"/api/knowledge/documents/{document_id}/chunks")
    search_response = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车",
            "faultText": "链条异响 张紧度",
            "inputType": "text",
            "topK": 5,
        },
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"id": document_id, "deleted": True}
    assert detail_response.status_code == 404
    assert chunks_response.status_code == 404
    results = search_response.json()["data"]["results"]
    assert not any(item.get("documentId") == document_id for item in results)


def test_delete_missing_knowledge_document_returns_404(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.delete("/api/knowledge/documents/kdoc-missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert "不存在" in payload["message"]


def test_knowledge_document_upload_rejects_empty_file(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.md", b"", "text/markdown")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "不能为空" in payload["message"]


def test_knowledge_document_upload_rejects_unsupported_extension(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.exe", b"unsafe", "application/octet-stream")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "仅支持" in payload["message"]


def test_knowledge_document_upload_rejects_oversized_file(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual.txt", b"x" * (20 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "20MB" in payload["message"]


def test_image_knowledge_document_can_be_multimodal_analyzed_and_searched(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("fault-photo.jpg", b"fake image bytes", "image/jpeg")},
        data={"source_name": "field-photo"},
    )
    assert upload_response.status_code == 200
    uploaded = upload_response.json()["data"]
    assert uploaded["status"] == "needs_multimodal_analysis"
    assert uploaded["chunkCount"] == 0

    analyze_response = client.post(f"/api/knowledge/documents/{uploaded['id']}/analyze", json={"provider": "mock"})
    assert analyze_response.status_code == 200
    analyzed = analyze_response.json()["data"]
    assert analyzed["status"] == "pending_review"
    assert analyzed["chunkCount"] > 0
    assert analyzed["pendingReviewCount"] == analyzed["chunkCount"]
    assert analyzed["analysis"]["provider"] == "mock"
    assert analyzed["analysis"]["fallback"] is True

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "A", "faultText": "mock", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert not any(item.get("documentId") == uploaded["id"] and item["sourceType"] == "document" for item in results)


def test_knowledge_chunk_revision_updates_chunk_and_revisions(tmp_path, monkeypatch) -> None:
    sync_calls: list[list[dict[str, Any]]] = []
    deleted: list[str] = []

    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: sync_calls.append(chunks))
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: deleted.append(document_id))
    client = make_client(tmp_path, monkeypatch)

    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("repair-note.txt", b"old spark plug note", "text/plain")},
        data={"source_name": "manual correction source"},
    )
    document = upload_response.json()["data"]
    chunk_id = document["chunks"][0]["id"]
    approve_response = client.patch(
        f"/api/knowledge/documents/{document['id']}/chunks/{chunk_id}/review",
        json={"action": "approve", "reviewer": "technician-a"},
    )
    assert approve_response.status_code == 200
    sync_calls.clear()
    deleted.clear()

    response = client.patch(
        f"/api/knowledge/documents/{document['id']}/chunks/{chunk_id}",
        json={
            "content": "修正后：火花塞积碳导致启动困难，应清洁或更换火花塞。",
            "tags": ["人工修正", "火花塞"],
            "reason": "现场技师确认 OCR/模型输出需要修正",
            "reviewer": "technician-a",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["chunk"]["content"].startswith("修正后")
    assert payload["chunk"]["manuallyCorrected"] is True
    assert payload["chunk"]["review_status"] == "pending_review"
    assert payload["chunk"]["supersedes"] == chunk_id
    assert payload["revision"]["before"]["content"] == "old spark plug note"
    assert "火花塞" in payload["revision"]["after"]["content"]
    assert deleted == []
    assert sync_calls == []

    revisions_response = client.get(f"/api/knowledge/documents/{document['id']}/revisions")
    revisions = revisions_response.json()["data"]
    assert revisions["total"] == 1
    assert revisions["items"][0]["reviewer"] == "technician-a"
    events = data_store.load_review_events()
    assert events[-1]["objectType"] == "knowledge_revision"
    assert events[-1]["revisionId"] == payload["revision"]["id"]
    assert events[-1]["before"]["content"] == "old spark plug note"
    assert "火花塞" in events[-1]["after"]["content"]
    assert events[-1]["reviewer"] == "technician-a"

    chunks_response = client.get(f"/api/knowledge/documents/{document['id']}/chunks")
    chunks = chunks_response.json()["data"]["items"]
    assert any(chunk["id"] == chunk_id and chunk["content"] == "old spark plug note" for chunk in chunks)
    assert any(chunk["id"] == payload["chunk"]["id"] and chunk["content"].startswith("修正后") for chunk in chunks)

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "发动机", "faultText": "火花塞积碳 启动困难", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert not any(item.get("chunkId") == chunk_id for item in results)


def test_mock_ocr_text_is_indexed_for_image_documents(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    client = make_client(tmp_path, monkeypatch)

    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("fault-code-photo.png", b"fake png bytes", "image/png")},
        data={"source_name": "fault-code-photo"},
    )
    document_id = upload_response.json()["data"]["id"]

    analyze_response = client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "mock"})

    assert analyze_response.status_code == 200
    analyzed = analyze_response.json()["data"]
    assert analyzed["analysis"]["ocr"]["provider"] == "mock"
    assert analyzed["analysis"]["ocr"]["fallback"] is True

    chunks_response = client.get(f"/api/knowledge/documents/{document_id}/chunks")
    chunks = chunks_response.json()["data"]["items"]
    assert any("OCR" in chunk["content"] or "跨模态检索" in chunk["content"] for chunk in chunks)

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "摩托车发动机", "faultText": "OCR 跨模态 火花塞", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert not any(item.get("documentId") == document_id for item in results)


def test_ocr_provider_missing_dependency_falls_back_to_mock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "rapidocr")
    monkeypatch.setattr(ocr_adapter, "rapidocr_text", lambda _: (_ for _ in ()).throw(ImportError("rapidocr missing")))
    client = make_client(tmp_path, monkeypatch)

    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("scan.webp", b"fake webp bytes", "image/webp")},
    )
    document_id = upload_response.json()["data"]["id"]

    response = client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "mock"})

    assert response.status_code == 200
    ocr = response.json()["data"]["analysis"]["ocr"]
    assert ocr["provider"] == "mock"
    assert ocr["requestedProvider"] == "rapidocr"
    assert ocr["fallback"] is True
    assert "rapidocr" in ocr["fallbackReason"]


def test_multimodal_analysis_falls_back_when_real_provider_is_unconfigured(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual-scan.png", b"fake png bytes", "image/png")},
    )
    document_id = upload_response.json()["data"]["id"]

    response = client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "openai"})

    assert response.status_code == 200
    analysis = response.json()["data"]["analysis"]
    assert analysis["provider"] == "mock"
    assert analysis["requestedProvider"] == "openai"
    assert analysis["fallback"] is True


def test_multimodal_analysis_remote_api_mode_off_skips_real_provider(tmp_path, monkeypatch) -> None:
    def fail_if_called(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("real multimodal provider should not be called while REMOTE_API_MODE=off")

    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(multimodal_adapter, "real_multimodal_analysis", fail_if_called)
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual-scan.png", b"fake png bytes", "image/png")},
    )
    document_id = upload_response.json()["data"]["id"]

    response = client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "openai"})

    assert response.status_code == 200
    analysis = response.json()["data"]["analysis"]
    assert analysis["provider"] == "mock"
    assert analysis["requestedProvider"] == "openai"
    assert analysis["fallback"] is True
    assert "REMOTE_API_MODE=off" in analysis["fallbackReason"]


def test_multimodal_analysis_network_error_falls_back_to_mock(tmp_path, monkeypatch) -> None:
    def fail_post_json(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("simulated multimodal timeout")

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(multimodal_adapter, "_post_json", fail_post_json)
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("manual-scan.png", b"fake png bytes", "image/png")},
    )
    document_id = upload_response.json()["data"]["id"]

    response = client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "openai"})

    assert response.status_code == 200
    analysis = response.json()["data"]["analysis"]
    assert analysis["provider"] == "mock"
    assert analysis["requestedProvider"] == "openai"
    assert analysis["fallback"] is True


def test_multimodal_analyzed_document_stays_pending_before_rag(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_response = client.post(
        "/api/knowledge/documents",
        files={"file": ("fault-photo.webp", b"fake webp bytes", "image/webp")},
        data={"source_name": "multimodal-field-data"},
    )
    document_id = upload_response.json()["data"]["id"]
    client.post(f"/api/knowledge/documents/{document_id}/analyze", json={"provider": "mock"})

    response = client.post(
        "/api/rag/answer",
        json={"deviceModel": "A", "faultText": "mock", "topK": 5, "provider": "mock"},
    )

    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert not any(item.get("documentId") == document_id for item in citations)


def test_multimodal_analysis_missing_document_returns_404(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/knowledge/documents/kdoc-missing/analyze", json={"provider": "mock"})

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None


def test_knowledge_graph_returns_nodes_and_edges(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/graph",
        json={"deviceModel": "A", "faultText": "A", "inputType": "text", "topK": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    graph = payload["data"]
    assert graph["nodes"]
    assert graph["edges"]
    assert any(node["type"] == "device" for node in graph["nodes"])
    assert any(node["type"] == "fault" for node in graph["nodes"])
    assert any(edge["relation"] for edge in graph["edges"])


def test_knowledge_graph_global_overview_and_rebuild(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    overview_response = client.get("/api/knowledge/graph")
    rebuild_response = client.post("/api/knowledge/graph/rebuild")

    assert overview_response.status_code == 200
    overview = overview_response.json()["data"]
    assert overview["mode"] == "global"
    assert overview["nodes"]
    assert overview["edges"]
    assert overview["stats"]["nodeCount"] == len(overview["nodes"])
    assert overview["recommendations"]

    assert rebuild_response.status_code == 200
    rebuilt = rebuild_response.json()["data"]
    assert rebuilt["mode"] == "global"
    assert rebuilt["stats"]["edgeCount"] == len(rebuilt["edges"])


def test_rag_answer_includes_graph_context(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "topK": 3,
            "provider": "mock",
            "includeGraphContext": True,
        },
    )

    assert response.status_code == 200
    graph_context = response.json()["data"]["graphContext"]
    assert graph_context["enabled"] is True
    assert graph_context["nodeCount"] > 0
    assert graph_context["edgeCount"] > 0
    assert graph_context["paths"]


def test_real_rag_prompt_receives_graph_context(tmp_path, monkeypatch) -> None:
    def fake_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        prompt = payload["messages"][0]["content"]
        assert "知识图谱关系上下文" in prompt
        assert "图谱规模" in prompt
        assert "G1." in prompt
        return {"choices": [{"message": {"content": "基于图谱证据链给出建议。[1]"}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "compatible-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible-provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setenv("OPENAI_API_STYLE", "chat_completions")
    monkeypatch.setattr(llm_adapter, "_post_json", fake_post_json)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "topK": 2,
            "provider": "openai",
            "includeGraphContext": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "openai"
    assert payload["fallback"] is False
    assert payload["graphContext"]["enabled"] is True


def test_knowledge_graph_rejects_empty_query(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/graph",
        json={"deviceModel": " ", "faultText": "", "inputType": "text", "topK": 5},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None


def test_fastapi_serves_frontend_dist_when_available(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Software Cup</title><div id=\"app\"></div>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setenv("SERVE_FRONTEND", "auto")
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist))
    client = make_client(tmp_path, monkeypatch)

    index_response = client.get("/")
    asset_response = client.get("/assets/app.js")
    api_response = client.get("/api/health")

    assert index_response.status_code == 200
    assert "Software Cup" in index_response.text
    assert asset_response.status_code == 200
    assert api_response.status_code == 200


def test_fastapi_frontend_serving_can_be_disabled(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("SERVE_FRONTEND", "off")
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist))
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/")

    assert response.status_code == 404
    assert response.json()["success"] is False


def test_search_vector_result_marks_hash_embedding_provider(tmp_path, monkeypatch) -> None:
    def fake_vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
        return [
            {
                "id": "kdoc-hash-chunk-001",
                "title": "离合器检查",
                "sourceType": "document",
                "sourceName": "Hash fallback 资料",
                "snippet": "离合器打滑时应检查间隙和磨损。",
                "documentId": "kdoc-hash",
                "chunkId": "kdoc-hash-chunk-001",
                "page": None,
                "distance": 0.2,
                "embeddingProvider": "hash",
            }
        ]

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setattr(vector_store, "search_similar_chunks", fake_vector_search)
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/search",
        json={"deviceModel": "摩托车", "faultText": "离合器打滑", "inputType": "text", "topK": 5},
    )

    assert response.status_code == 200
    item = next(result for result in response.json()["data"]["results"] if result["id"] == "kdoc-hash-chunk-001")
    assert item["scoreBreakdown"]["embeddingProvider"] == "hash"
    assert "hash fallback" in item["reason"]


def test_vector_sync_uses_openai_embedding_when_available(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeCollection:
        def upsert(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    def fake_post_json(*_: Any, **__: Any) -> dict[str, Any]:
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    def fake_collection(provider: str) -> FakeCollection:
        captured["collectionProvider"] = provider
        return FakeCollection()

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(vector_store, "_post_json", fake_post_json)
    monkeypatch.setattr(vector_store, "chroma_collection", fake_collection)

    vector_store.sync_chunks(
        [
            {
                "id": "chunk-001",
                "documentId": "doc-001",
                "title": "测试资料",
                "sourceName": "测试",
                "content": "发动机启动困难",
                "snippet": "发动机启动困难",
                "review_status": "approved",
                "is_current": True,
            }
        ]
    )

    assert captured["collectionProvider"] == "openai"
    assert captured["embeddings"] == [[0.1, 0.2, 0.3]]
    assert captured["metadatas"][0]["embeddingProvider"] == "openai"


def test_vector_store_defaults_to_sqlite_with_current_embedding_model(monkeypatch) -> None:
    monkeypatch.delenv("RAG_VECTOR_STORE", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

    assert vector_store.vector_store_enabled() is True
    assert vector_store.vector_store_kind() == "sqlite"
    assert vector_store.embedding_model() == "text-embedding-3-small"


def test_vector_sync_falls_back_to_hash_embedding_when_remote_fails(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeCollection:
        def upsert(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    def fail_post_json(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("simulated embedding outage")

    def fake_collection(provider: str) -> FakeCollection:
        captured["collectionProvider"] = provider
        return FakeCollection()

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(vector_store, "_post_json", fail_post_json)
    monkeypatch.setattr(vector_store, "chroma_collection", fake_collection)

    vector_store.sync_chunks(
        [
            {
                "id": "chunk-001",
                "documentId": "doc-001",
                "title": "测试资料",
                "sourceName": "测试",
                "content": "发动机启动困难",
                "snippet": "发动机启动困难",
                "review_status": "approved",
                "is_current": True,
            }
        ]
    )

    assert captured["collectionProvider"] == "hash"
    assert captured["metadatas"][0]["embeddingProvider"] == "hash"
    assert captured["embeddings"][0]


def test_json_vector_store_indexes_only_approved_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "json")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")

    vector_store.sync_chunks(
        [
            {
                "id": "chunk-approved",
                "documentId": "doc-approved",
                "title": "LoongArch PDF 资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "发动机启动困难 怠速不稳 点火系统检查",
                "snippet": "发动机启动困难 怠速不稳",
                "review_status": "approved",
            },
            {
                "id": "chunk-pending",
                "documentId": "doc-pending",
                "title": "待审核资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "pending review should not be indexed",
                "snippet": "pending review",
                "review_status": "pending_review",
            },
        ]
    )

    results = vector_store.search_similar_chunks("启动困难 怠速不稳", 5)

    assert vector_store.json_vector_index_path().exists()
    assert [item["chunkId"] for item in results] == ["chunk-approved"]
    assert results[0]["embeddingProvider"] == "hash"


def test_sqlite_vector_store_indexes_only_approved_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "sqlite")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")

    vector_store.sync_chunks(
        [
            {
                "id": "sqlite-chunk-approved",
                "documentId": "sqlite-doc-approved",
                "title": "SQLite 目标环境资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "液压泵异响 油液污染 过滤器堵塞",
                "snippet": "液压泵异响 油液污染",
                "review_status": "approved",
            },
            {
                "id": "sqlite-chunk-pending",
                "documentId": "sqlite-doc-pending",
                "title": "待审核资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "pending sqlite vector data must not be indexed",
                "snippet": "pending sqlite",
                "review_status": "pending_review",
            },
        ]
    )

    results = vector_store.search_similar_chunks("液压泵 异响 油液污染", 5)

    assert vector_store.sqlite_vector_index_path().exists()
    assert [item["chunkId"] for item in results] == ["sqlite-chunk-approved"]
    assert results[0]["embeddingProvider"] == "hash"


def test_sqlite_vec_request_falls_back_to_python_scan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "sqlite")
    monkeypatch.setenv("RAG_VECTOR_SQLITE_ENGINE", "sqlite_vec")
    monkeypatch.setenv("SQLITE_VEC_EXTENSION_PATH", str(tmp_path / "missing-sqlite-vec.so"))
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")

    vector_store.sync_chunks(
        [
            {
                "id": "sqlite-vec-fallback-approved",
                "documentId": "sqlite-vec-doc",
                "title": "sqlite-vec fallback 资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "轴承温升异常 润滑不足 检查油脂",
                "snippet": "轴承温升异常",
                "review_status": "approved",
            }
        ]
    )

    status = vector_store.vector_backend_status()
    results = vector_store.search_similar_chunks("轴承 温升 润滑", 5)

    assert status["sqliteEngine"]["requested"] == "sqlite_vec"
    assert status["sqliteEngine"]["effective"] == "python_scan"
    assert status["sqliteEngine"]["status"] == "fallback"
    assert [item["chunkId"] for item in results] == ["sqlite-vec-fallback-approved"]


def test_qdrant_enhancer_unavailable_keeps_sqlite_local_results(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "sqlite")
    monkeypatch.setenv("RAG_VECTOR_ENHANCER", "qdrant")
    monkeypatch.setenv("RAG_VECTOR_FALLBACK_LOCAL", "on")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")
    monkeypatch.setattr(vector_store, "search_qdrant", lambda *_args, **_kwargs: [])

    vector_store.sync_chunks(
        [
            {
                "id": "qdrant-fallback-approved",
                "documentId": "qdrant-doc",
                "title": "Qdrant fallback 资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "液压缸爬行 密封磨损 空气进入系统",
                "snippet": "液压缸爬行",
                "review_status": "approved",
            }
        ]
    )

    results = vector_store.search_similar_chunks("液压缸 爬行 密封", 5)

    assert [item["chunkId"] for item in results] == ["qdrant-fallback-approved"]
    assert results[0]["retrievalSource"] == "sqlite"


def test_json_vector_store_delete_document_removes_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "json")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")

    vector_store.sync_chunks(
        [
            {
                "id": "chunk-delete",
                "documentId": "doc-delete",
                "title": "待删除资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "制动泵渗漏 检查密封圈",
                "snippet": "制动泵渗漏",
                "review_status": "approved",
            }
        ]
    )

    assert vector_store.search_similar_chunks("制动泵渗漏", 5)
    vector_store.delete_document("doc-delete")

    assert vector_store.search_similar_chunks("制动泵渗漏", 5) == []


def test_sqlite_vector_store_delete_document_removes_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("RAG_VECTOR_STORE", "sqlite")
    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "hash")

    vector_store.sync_chunks(
        [
            {
                "id": "sqlite-chunk-delete",
                "documentId": "sqlite-doc-delete",
                "title": "待删除资料",
                "sourceName": "目标环境资料",
                "sourceType": "document",
                "content": "冷却风扇不转 检查继电器和保险丝",
                "snippet": "冷却风扇不转",
                "review_status": "approved",
            }
        ]
    )

    assert vector_store.search_similar_chunks("冷却风扇 继电器", 5)
    vector_store.delete_document("sqlite-doc-delete")

    assert vector_store.search_similar_chunks("冷却风扇 继电器", 5) == []


def test_multimodal_validate_mock_provider(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/providers/multimodal/validate", json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "mock"
    assert data["fallback"] is True
    assert data["summaryPreview"]


def test_multimodal_validate_remote_mode_off_skips_provider(tmp_path, monkeypatch) -> None:
    def fail_if_called(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("remote multimodal provider should not be called")

    monkeypatch.setenv("REMOTE_API_MODE", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(multimodal_adapter, "real_multimodal_analysis", fail_if_called)
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/providers/multimodal/validate", json={"provider": "openai"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["remoteOk"] is False
    assert data["fallback"] is True
    assert "REMOTE_API_MODE=off" in data["fallbackReason"]


def test_multimodal_validate_real_provider_mock_success(tmp_path, monkeypatch) -> None:
    def fake_real_multimodal(*_: Any, **__: Any) -> dict[str, Any]:
        return {"summary": "真实多模态 API 小样本验收通过。"}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(multimodal_adapter, "real_multimodal_analysis", fake_real_multimodal)
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/api/providers/multimodal/validate", json={"provider": "openai"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["remoteOk"] is True
    assert data["fallback"] is False
    assert "验收通过" in data["summaryPreview"]


def test_json_writes_use_atomic_replace(tmp_path, monkeypatch) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(examples))
    calls: list[tuple[str, str]] = []

    def fake_replace(src: Any, dst: Any) -> None:
        calls.append((str(src), str(dst)))

    monkeypatch.setattr(data_store.os, "replace", fake_replace)

    data_store.save_cases([{"id": "case-atomic"}])

    assert calls
    temp_path, target_path = calls[0]
    assert temp_path.endswith(".tmp")
    assert target_path.endswith("repair-cases.json")
    assert "case-atomic" in (examples / "repair-cases.json").with_name(Path(temp_path).name).read_text(
        encoding="utf-8"
    )


def test_chroma_collection_creation_failure_degrades_gracefully(tmp_path, monkeypatch) -> None:
    class BrokenClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            raise RuntimeError("simulated chroma init failure")

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("APP_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setitem(__import__("sys").modules, "chromadb", type("FakeChroma", (), {"PersistentClient": BrokenClient}))

    assert vector_store.search_similar_chunks("发动机 启动困难", 3) == []


def test_chroma_query_failure_degrades_gracefully(monkeypatch) -> None:
    class BrokenCollection:
        def query(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError("simulated query failure")

    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setattr(vector_store, "chroma_collection", lambda provider: BrokenCollection())

    assert vector_store.search_similar_chunks("发动机 启动困难", 3) == []
