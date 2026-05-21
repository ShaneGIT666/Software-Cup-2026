from __future__ import annotations

import json
import shutil
from typing import Any

from fastapi.testclient import TestClient

import backend.app.llm_adapter as llm_adapter
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


def test_knowledge_document_upload_indexes_text_and_is_searchable(tmp_path, monkeypatch) -> None:
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
    assert payload["data"]["status"] == "indexed"
    assert payload["data"]["chunkCount"] == 1

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
    assert any(item["sourceType"] == "document" and item["sourceName"] == "摩托车检修手册" for item in results)


def test_rag_answer_uses_ingested_document_citation(tmp_path, monkeypatch) -> None:
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
    assert any(item["sourceType"] == "document" and item["sourceName"] == "摩托车检修手册" for item in citations)


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
    assert analyzed["status"] == "analyzed"
    assert analyzed["chunkCount"] > 0
    assert analyzed["analysis"]["provider"] == "mock"
    assert analyzed["analysis"]["fallback"] is True

    search_response = client.post(
        "/api/search",
        json={"deviceModel": "A", "faultText": "mock", "inputType": "text", "topK": 5},
    )
    results = search_response.json()["data"]["results"]
    assert any(item.get("documentId") == uploaded["id"] and item["sourceType"] == "document" for item in results)


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


def test_multimodal_analyzed_document_is_used_by_rag(tmp_path, monkeypatch) -> None:
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
    assert any(item.get("documentId") == document_id for item in citations)


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
