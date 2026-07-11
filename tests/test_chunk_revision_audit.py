from __future__ import annotations

import shutil
from typing import Any

from fastapi.testclient import TestClient

import backend.app.data_store as data_store
import backend.app.knowledge as knowledge
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("MINERU_ENABLED", "false")
    return TestClient(app)


def test_chunk_revision_creates_pending_version_and_replaces_after_approval(tmp_path, monkeypatch) -> None:
    sync_calls: list[list[dict[str, Any]]] = []
    deleted_documents: list[str] = []
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: sync_calls.append(chunks))
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: deleted_documents.append(document_id))
    client = make_client(tmp_path, monkeypatch)

    upload = client.post(
        "/api/knowledge/documents",
        files={"file": ("field-note.txt", b"old pressure note", "text/plain")},
        data={"source_name": "field"},
    ).json()["data"]
    document_id = upload["id"]
    chunk_id = upload["chunks"][0]["id"]

    approve_v1 = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}/review",
        json={"action": "approve", "reviewer": "reviewer-a"},
    )
    assert approve_v1.status_code == 200
    assert approve_v1.json()["data"]["chunk"]["review_status"] == "approved"
    assert sync_calls and sync_calls[-1][0]["id"] == chunk_id

    sync_calls.clear()
    deleted_documents.clear()

    revision_response = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}",
        json={
            "content": "new pressure note review required",
            "tags": ["manual-correction", "pressure"],
            "reason": "line review correction",
            "reviewer": "reviewer-a",
        },
    )

    assert revision_response.status_code == 200
    payload = revision_response.json()["data"]
    proposed_id = payload["proposedChunk"]["id"]
    assert payload["revision"]["reviewer"] == "reviewer-a"
    assert payload["revision"]["status"] == "pending_review"
    assert payload["originalChunk"]["id"] == chunk_id
    assert proposed_id != chunk_id
    assert payload["proposedChunk"]["supersedes"] == chunk_id
    assert payload["proposedChunk"]["version"] == 2
    assert payload["proposedChunk"]["review_status"] == "pending_review"
    assert payload["proposedChunk"]["is_current"] is False
    assert payload["proposedChunk"]["manuallyCorrected"] is True
    assert deleted_documents == []
    assert sync_calls == []

    chunks_after_revision = data_store.load_document_chunks()
    original = next(chunk for chunk in chunks_after_revision if chunk["id"] == chunk_id)
    proposed = next(chunk for chunk in chunks_after_revision if chunk["id"] == proposed_id)
    assert original["content"] == "old pressure note"
    assert original["review_status"] == "approved"
    assert original["is_current"] is True
    assert proposed["review_status"] == "pending_review"

    old_search = client.post("/api/search", json={"faultText": "old pressure note", "topK": 5}).json()["data"]
    new_search = client.post("/api/search", json={"faultText": "new pressure note", "topK": 5}).json()["data"]
    assert any(item.get("chunkId") == chunk_id for item in old_search["results"])
    assert all(item.get("chunkId") != proposed_id for item in new_search["results"])

    events = data_store.load_review_events()
    assert events[-1]["objectType"] == "knowledge_revision"
    assert events[-1]["objectId"] == payload["revision"]["id"]
    assert events[-1]["revisionId"] == payload["revision"]["id"]
    assert events[-1]["reviewer"] == "reviewer-a"
    assert events[-1]["supersedes"] == chunk_id

    approve_v2 = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "approve", "reviewer": "reviewer-b"},
    )
    assert approve_v2.status_code == 200
    assert deleted_documents == [document_id]
    assert sync_calls and sync_calls[-1][0]["id"] == proposed_id

    chunks_after_approval = data_store.load_document_chunks()
    original_after = next(chunk for chunk in chunks_after_approval if chunk["id"] == chunk_id)
    proposed_after = next(chunk for chunk in chunks_after_approval if chunk["id"] == proposed_id)
    assert original_after["review_status"] == "replaced"
    assert original_after["is_current"] is False
    assert original_after["replaced_by"] == proposed_id
    assert proposed_after["review_status"] == "approved"
    assert proposed_after["is_current"] is True

    old_search_after = client.post("/api/search", json={"faultText": "old pressure note", "topK": 5}).json()["data"]
    new_search_after = client.post("/api/search", json={"faultText": "new pressure note", "topK": 5}).json()["data"]
    assert all(item.get("chunkId") != chunk_id for item in old_search_after["results"])
    assert any(item.get("chunkId") == proposed_id for item in new_search_after["results"])


def test_rejecting_revision_keeps_original_current(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    client = make_client(tmp_path, monkeypatch)

    upload = client.post(
        "/api/knowledge/documents",
        files={"file": ("field-note.txt", b"old pressure note", "text/plain")},
        data={"source_name": "field"},
    ).json()["data"]
    document_id = upload["id"]
    chunk_id = upload["chunks"][0]["id"]
    client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}/review",
        json={"action": "approve", "reviewer": "reviewer-a"},
    )
    revision = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}",
        json={"content": "new pressure note", "reason": "bad correction", "reviewer": "reviewer-a"},
    ).json()["data"]
    proposed_id = revision["proposedChunk"]["id"]

    reject = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "reject", "reason": "not grounded", "reviewer": "reviewer-b"},
    )

    assert reject.status_code == 200
    chunks = data_store.load_document_chunks()
    original = next(chunk for chunk in chunks if chunk["id"] == chunk_id)
    proposed = next(chunk for chunk in chunks if chunk["id"] == proposed_id)
    assert original["review_status"] == "approved"
    assert original["is_current"] is True
    assert proposed["review_status"] == "rejected"
    assert proposed["is_current"] is False
