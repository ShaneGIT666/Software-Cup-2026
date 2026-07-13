from __future__ import annotations

from io import BytesIO
import shutil

from fastapi.testclient import TestClient
from pypdf import PdfWriter

import backend.app.data_store as data_store
import backend.app.knowledge as knowledge
import backend.app.manual_visual_pipeline as pipeline
import backend.app.system_status as system_status
from backend.app.main import app


def pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_client(tmp_path, monkeypatch) -> TestClient:
    examples = tmp_path / "examples"
    shutil.copytree("data/examples", examples)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(examples))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ALLOW_INSECURE_AUTH_OFF", "true")
    return TestClient(app)


def parsed_text_result() -> dict[str, object]:
    return {
        "parser": "pypdf",
        "status": "parsed",
        "pages": [{"page": 1, "section": "page-1", "text": "ignition system inspection procedure"}],
        "markdown": "ignition system inspection procedure",
        "assets": [],
        "mineruAssets": [],
        "mineruAttempted": True,
        "mineruSucceeded": False,
        "fallback": True,
        "fallbackReason": "MinerU parsing failed; fallback parser used.",
    }


def unavailable_readiness() -> dict[str, object]:
    return {
        "ready": False,
        "renderer": "unavailable",
        "status": "unavailable",
        "commandFound": False,
        "versionProbeOk": False,
        "smokeRenderOk": False,
        "failureCategory": "not_found",
    }


def test_smart_preserves_text_and_completes_with_warning(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(knowledge, "parse_document", lambda *args, **kwargs: parsed_text_result())
    monkeypatch.setattr(pipeline, "renderer_operational_readiness", unavailable_readiness)

    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("manual.pdf", pdf_bytes(), "application/pdf")},
        data={"parser_mode": "smart_multimodal"},
    )
    assert response.status_code == 200
    task_id = response.json()["data"]["id"]
    task = client.get(f"/api/knowledge/parse-tasks/{task_id}").json()["data"]
    document = data_store.load_documents()[0]
    chunks = data_store.load_document_chunks()

    assert task["status"] == "completed_with_warnings"
    assert task["visualFailureReason"] == "PDF renderer is unavailable; text knowledge was preserved."
    assert document["status"] == "pending_review"
    assert document["textChunkCount"] > 0
    assert document["chunkCount"] == document["textChunkCount"]
    assert document["visualAnalysisStatus"] == "completed_with_warnings"
    assert document["assetAnalysisStatus"] == "fallback_completed"
    assert document["renderer"] == "unavailable"
    assert document["visualPagesRendered"] == 0
    assert document["visualChunkCount"] == 0
    assert document["parserFallbackReason"] == "MinerU parsing failed; fallback parser used."
    assert not any(chunk.get("origin") == "manual_visual_pipeline" for chunk in chunks)


def test_full_rejects_before_task_document_or_queue_write(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(knowledge, "renderer_operational_readiness", unavailable_readiness)
    queue_dir = tmp_path / "knowledge" / "parse-queue"

    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("manual.pdf", pdf_bytes(), "application/pdf")},
        data={"parser_mode": "full_visual"},
    )
    assert response.status_code == 503
    assert response.json()["message"] == "full_visual requires an operational PDF renderer"
    assert data_store.load_parse_tasks() == []
    assert data_store.load_documents() == []
    assert not queue_dir.exists() or list(queue_dir.iterdir()) == []


def test_text_fast_rejects_image_before_task_creation(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("photo.png", b"valid-image-placeholder", "image/png")},
        data={"parser_mode": "text_fast"},
    )
    assert response.status_code == 422
    assert response.json()["message"] == (
        "text_fast does not process image files; use smart_multimodal or full_visual"
    )
    assert data_store.load_parse_tasks() == []
    assert data_store.load_documents() == []


def test_new_visual_status_never_reports_completed_with_queued_asset(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(knowledge, "parse_document", lambda *args, **kwargs: parsed_text_result())
    monkeypatch.setattr(pipeline, "renderer_operational_readiness", unavailable_readiness)
    client.post(
        "/api/knowledge/documents/async",
        files={"file": ("manual.pdf", pdf_bytes(), "application/pdf")},
        data={"parser_mode": "smart_multimodal"},
    )
    for document in data_store.load_documents():
        assert not (
            document.get("visualAnalysisStatus") == "completed"
            and document.get("assetAnalysisStatus") == "queued"
        )


def test_system_status_uses_multimodal_readiness_without_credentials(monkeypatch) -> None:
    readiness = {
        "provider": "local",
        "model": "local-model",
        "credentialConfigured": True,
        "endpointConfigured": True,
        "remoteAllowed": True,
        "ready": True,
        "status": "ready",
    }
    monkeypatch.setattr(system_status, "multimodal_readiness", lambda: readiness)
    status = system_status.manual_visual_status()
    assert status["realMultimodalConfigured"] is True
    assert status["multimodalReadiness"] == readiness
    assert "apiKey" not in str(status)
    assert "baseUrl" not in str(status)
