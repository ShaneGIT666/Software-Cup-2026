from __future__ import annotations

import json
import shutil
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


def test_provider_status_defaults_to_openai_embedding_with_hash_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("REMOTE_API_MODE", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    embedding = response.json()["data"]["embedding"]
    assert embedding["provider"] == "openai"
    assert embedding["vectorStore"] == "chroma"
    assert embedding["remoteCapable"] is True
    assert embedding["keyConfigured"] is False
    assert embedding["effectiveProvider"] == "hash"
    assert embedding["model"] == "text-embedding-3-small"


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
    assert "基于已检索到" in payload["data"]["answer"]


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
    assert payload["answer"] == "这是 OpenAI provider 返回的检修建议。"


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
    assert payload["answer"] == "这是兼容 OpenAI Chat Completions 的模型返回。"
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
    assert payload["answer"] == "这是 Anthropic provider 返回的检修建议。"


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
    assert payload["answer"] == "环境变量 provider 生效。"


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


def test_invalid_review_action_is_rejected_without_status_change(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    pending_response = client.get("/api/cases?status=pending_review")
    pending_case = pending_response.json()["data"]["items"][0]

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
        assert top_k == 5
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
    assert payload["revision"]["before"]["content"] == "old spark plug note"
    assert "火花塞" in payload["revision"]["after"]["content"]
    assert deleted == [document["id"]]
    assert sync_calls and sync_calls[-1][0]["id"] == chunk_id

    revisions_response = client.get(f"/api/knowledge/documents/{document['id']}/revisions")
    revisions = revisions_response.json()["data"]
    assert revisions["total"] == 1
    assert revisions["items"][0]["reviewer"] == "technician-a"

    chunks_response = client.get(f"/api/knowledge/documents/{document['id']}/chunks")
    chunks = chunks_response.json()["data"]["items"]
    assert chunks[0]["content"].startswith("修正后")

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
            }
        ]
    )

    assert captured["collectionProvider"] == "openai"
    assert captured["embeddings"] == [[0.1, 0.2, 0.3]]
    assert captured["metadatas"][0]["embeddingProvider"] == "openai"


def test_vector_store_defaults_to_chroma_with_current_embedding_model(monkeypatch) -> None:
    monkeypatch.delenv("RAG_VECTOR_STORE", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

    assert vector_store.vector_store_enabled() is True
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
            }
        ]
    )

    assert captured["collectionProvider"] == "hash"
    assert captured["metadatas"][0]["embeddingProvider"] == "hash"
    assert captured["embeddings"][0]


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
    assert "case-atomic" in (examples / "repair-cases.json").with_name(temp_path.split("\\")[-1]).read_text(
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
