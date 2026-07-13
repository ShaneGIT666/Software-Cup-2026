from __future__ import annotations

import shutil

from fastapi.testclient import TestClient

import backend.app.data_store as data_store
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    knowledge_root = tmp_path / "knowledge"
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(knowledge_root))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("AUTH_OPERATOR_TOKEN", "operator-test-token")
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", "reviewer-test-token")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "admin-test-token")
    asset = knowledge_root / "parsed" / "kdoc-visual" / "visual-assets" / "page-0001.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"jpeg-data")
    data_store.save_documents(
        [
            {
                "id": "kdoc-visual",
                "fileName": "visual-manual.pdf",
                "fileType": "application/pdf",
                "suffix": "pdf",
                "sourceName": "visual manual",
                "status": "pending_review",
                "chunkCount": 1,
                "pendingReviewCount": 1,
                "parser": "pypdf",
                "uploadedAt": "2026-07-13T00:00:00Z",
            }
        ]
    )
    data_store.save_document_chunks(
        [
            {
                "id": "kdoc-visual-visual-page-0001",
                "documentId": "kdoc-visual",
                "assetId": "page-0001",
                "assetRelativePath": "visual-assets/page-0001.jpg",
                "assetType": "page_visual",
                "origin": "manual_visual_pipeline",
                "sourceType": "document_asset",
                "source_type": "document_asset",
                "sourceName": "visual manual",
                "source_doc_id": "kdoc-visual",
                "chunk_id": "kdoc-visual-visual-page-0001",
                "title": "Ignition coil visual evidence",
                "content": "visual-only-ignition-coil inspection connector",
                "snippet": "visual-only-ignition-coil inspection connector",
                "page": 1,
                "section": "pdf-page-1",
                "previewUrl": "/api/knowledge/documents/kdoc-visual/visual-assets/page-0001/file",
                "visualType": "wiring_diagram",
                "semanticVerified": True,
                "analysisProvider": "openai",
                "analysisFallback": False,
                "review_status": "pending_review",
                "is_current": False,
                "version": 1,
                "logical_chunk_id": "kdoc-visual-visual-page-0001",
            }
        ]
    )
    return TestClient(app)


def test_visual_asset_requires_auth_and_all_roles_can_read(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    path = "/api/knowledge/documents/kdoc-visual/visual-assets/page-0001/file"
    assert client.get(path).status_code == 401
    for token in ("operator-test-token", "reviewer-test-token", "admin-test-token"):
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/jpeg")
        assert b"knowledge" not in response.content


def test_visual_asset_rejects_invalid_id_and_traversal(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer operator-test-token"}
    invalid = client.get(
        "/api/knowledge/documents/kdoc-visual/visual-assets/not-valid/file",
        headers=headers,
    )
    assert invalid.status_code == 404
    chunks = data_store.load_document_chunks()
    chunks[0]["assetRelativePath"] = "../../outside.jpg"
    data_store.save_document_chunks(chunks)
    traversal = client.get(
        "/api/knowledge/documents/kdoc-visual/visual-assets/page-0001/file",
        headers=headers,
    )
    assert traversal.status_code == 404


def test_visual_chunk_is_searchable_only_after_review_with_metadata(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    query = {
        "deviceModel": "motorcycle",
        "faultText": "visual-only-ignition-coil connector",
        "maintenanceLevel": "normal_repair",
        "inputType": "text",
        "topK": 10,
    }
    operator = {"Authorization": "Bearer operator-test-token"}
    reviewer = {"Authorization": "Bearer reviewer-test-token"}
    before = client.post("/api/search", json=query, headers=operator)
    assert before.status_code == 200
    assert not any(item.get("chunkId") == "kdoc-visual-visual-page-0001" for item in before.json()["data"]["results"])

    review = client.patch(
        "/api/knowledge/documents/kdoc-visual/chunks/kdoc-visual-visual-page-0001/review",
        json={"action": "approve", "reason": "verified", "reviewer": "reviewer"},
        headers=reviewer,
    )
    assert review.status_code == 200
    after = client.post("/api/search", json=query, headers=operator)
    match = next(
        item
        for item in after.json()["data"]["results"]
        if item.get("chunkId") == "kdoc-visual-visual-page-0001"
    )
    assert match["page"] == 1
    assert match["previewUrl"].endswith("/page-0001/file")
    assert match["semanticVerified"] is True
    assert match["analysisProvider"] == "openai"
    assert match["analysisFallback"] is False
