from __future__ import annotations

import shutil

from fastapi.testclient import TestClient
import pytest

import backend.app.data_store as data_store
import backend.app.manual_visual_pipeline as pipeline
import backend.app.multimodal_adapter as multimodal
import backend.app.parser_router as parser_router
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    examples = tmp_path / "examples"
    shutil.copytree("data/examples", examples)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(examples))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("AUTH_OPERATOR_TOKEN", "operator-test-token")
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", "reviewer-test-token")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("MULTIMODAL_PROVIDER", "openai")
    monkeypatch.setenv("MULTIMODAL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MULTIMODAL_OPENAI_MODEL", "test-model")
    monkeypatch.setenv("REMOTE_API_MODE", "auto")
    return TestClient(app)


def install_analysis_mocks(monkeypatch) -> tuple[list[str], list[str]]:
    ocr_calls: list[str] = []
    multimodal_calls: list[str] = []

    def fake_ocr(file_path, source_name, suffix):
        ocr_calls.append(suffix)
        return {"text": "ignition connector", "textSegments": ["ignition connector"]}

    def fake_real(file_path, source_name, suffix, provider, **kwargs):
        multimodal_calls.append(suffix)
        return {
            "visualType": "wiring_diagram",
            "summary": "ignition connector wiring",
            "components": ["ignition connector"],
            "operations": ["inspect connector"],
            "figureLabels": [],
            "safetyWarnings": [],
            "uncertainties": [],
            "textSegments": ["ignition connector wiring"],
            "provider": "openai",
            "model": "test-model",
            "fallback": False,
            "fallbackReason": "",
            "semanticVerified": True,
            "imageInputSent": True,
        }

    monkeypatch.setattr(multimodal, "analyze_ocr_document", fake_ocr)
    monkeypatch.setattr(multimodal, "real_multimodal_analysis", fake_real)
    monkeypatch.setattr(
        pipeline,
        "render_pdf_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("renderer must not run")),
    )
    monkeypatch.setattr(
        parser_router,
        "parse_with_mineru",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("MinerU must not run")),
    )
    return ocr_calls, multimodal_calls


@pytest.mark.parametrize("mode", ["smart_multimodal", "full_visual"])
def test_image_document_uses_async_visual_pipeline(tmp_path, monkeypatch, mode: str) -> None:
    client = make_client(tmp_path, monkeypatch)
    ocr_calls, multimodal_calls = install_analysis_mocks(monkeypatch)
    operator = {"Authorization": "Bearer operator-test-token"}

    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("wiring.png", b"image-bytes", "image/png")},
        data={"parser_mode": mode},
        headers=operator,
    )
    assert response.status_code == 200
    task_id = response.json()["data"]["id"]
    task = client.get(f"/api/knowledge/parse-tasks/{task_id}", headers=operator).json()["data"]
    document = data_store.load_documents()[0]
    chunk = data_store.load_document_chunks()[0]

    assert task["status"] == "completed"
    assert ocr_calls == ["png"]
    assert multimodal_calls == ["png"]
    assert document["pageCount"] == 1
    assert document["visualCandidatePages"] == 1
    assert document["visualPagesRendered"] == 0
    assert document["visualPagesOcrProcessed"] == 1
    assert document["visualPagesAnalyzed"] == 1
    assert document["realMultimodalPages"] == 1
    assert document["fallbackVisualPages"] == 0
    assert document["visualCoverageRatio"] == 1.0
    assert document["realMultimodalCoverageRatio"] == 1.0
    assert document["visualChunkCount"] == 1
    assert document["renderer"] == "not_required"
    assert document["assetAnalysisStatus"] == "completed"
    assert chunk["assetId"] == "image-0001"
    assert chunk["assetType"] == "uploaded_image"
    assert chunk["knowledge_type"] == "manual_figure_asset"
    assert chunk["section"] == "uploaded-image"
    assert chunk["review_status"] == "pending_review"
    assert chunk["is_current"] is False
    assert chunk["semanticVerified"] is True
    assert chunk["previewUrl"].endswith("/image-0001/file")
    assert not str(chunk["assetRelativePath"]).startswith(str(tmp_path))

    preview_path = chunk["previewUrl"]
    assert client.get(preview_path).status_code == 401
    preview = client.get(preview_path, headers=operator)
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")


def test_image_chunk_is_retrievable_only_after_review(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    install_analysis_mocks(monkeypatch)
    operator = {"Authorization": "Bearer operator-test-token"}
    reviewer = {"Authorization": "Bearer reviewer-test-token"}
    client.post(
        "/api/knowledge/documents/async",
        files={"file": ("wiring.jpg", b"image-bytes", "image/jpeg")},
        data={"parser_mode": "smart_multimodal"},
        headers=operator,
    )
    document = data_store.load_documents()[0]
    chunk = data_store.load_document_chunks()[0]
    query = {
        "deviceModel": "motorcycle",
        "faultText": "ignition connector wiring",
        "maintenanceLevel": "normal_repair",
        "inputType": "text",
        "topK": 10,
    }
    before = client.post("/api/search", json=query, headers=operator).json()["data"]["results"]
    assert not any(item.get("chunkId") == chunk["id"] for item in before)

    review = client.patch(
        f"/api/knowledge/documents/{document['id']}/chunks/{chunk['id']}/review",
        json={"action": "approve", "reason": "verified", "reviewer": "reviewer"},
        headers=reviewer,
    )
    assert review.status_code == 200
    after = client.post("/api/search", json=query, headers=operator).json()["data"]["results"]
    match = next(item for item in after if item.get("chunkId") == chunk["id"])
    assert match["page"] is None
    assert match["previewUrl"].endswith("/image-0001/file")
    assert match["semanticVerified"] is True
    assert match["analysisProvider"] == "openai"
    assert match["analysisFallback"] is False
