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


def test_document_review_summary_does_not_keep_indexed_for_mixed_terminal_states() -> None:
    document = {"id": "doc-1", "status": "indexed"}
    knowledge.update_document_review_summary(
        document,
        [
            {"id": "c1", "review_status": "rejected", "is_current": False},
            {"id": "c2", "review_status": "deprecated", "is_current": False},
        ],
    )

    assert document["status"] == "pending_review"
    assert document["currentApprovedCount"] == 0


def test_document_review_summary_does_not_index_noncurrent_approved_chunk() -> None:
    document = {"id": "doc-1", "status": "indexed"}
    knowledge.update_document_review_summary(
        document,
        [{"id": "c1", "review_status": "approved", "is_current": False}],
    )

    assert document["status"] != "indexed"
    assert document["currentApprovedCount"] == 0


def test_document_review_summary_does_not_keep_indexed_when_chunks_are_empty() -> None:
    document = {"id": "doc-1", "status": "indexed"}
    knowledge.update_document_review_summary(document, [])

    assert document["status"] == "pending_review"
    assert document["chunkCount"] == 0


def test_document_review_summary_indexes_current_approved_chunk() -> None:
    document = {"id": "doc-1", "status": "pending_review"}
    knowledge.update_document_review_summary(
        document,
        [{"id": "c1", "review_status": "approved", "is_current": True}],
    )

    assert document["status"] == "indexed"
    assert document["currentApprovedCount"] == 1


def upload_and_approve_chunk(client: TestClient) -> tuple[str, str]:
    upload = client.post(
        "/api/knowledge/documents",
        files={"file": ("field-note.txt", b"old pressure note", "text/plain")},
        data={"source_name": "field"},
    ).json()["data"]
    document_id = upload["id"]
    chunk_id = upload["chunks"][0]["id"]
    approve = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}/review",
        json={"action": "approve", "reviewer": "reviewer-a"},
    )
    assert approve.status_code == 200
    return document_id, chunk_id


def propose_revision(client: TestClient, document_id: str, chunk_id: str, content: str = "new pressure note") -> str:
    revision = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}",
        json={"content": content, "reason": "line review correction", "reviewer": "reviewer-a"},
    )
    assert revision.status_code == 200
    return revision.json()["data"]["proposedChunk"]["id"]


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
    assert len(
        [
            chunk
            for chunk in chunks_after_approval
            if (chunk.get("logical_chunk_id") or chunk.get("id")) == chunk_id
            and chunk.get("review_status") == "approved"
            and chunk.get("is_current") is True
        ]
    ) == 1

    revisions_after_approval = data_store.load_knowledge_revisions()
    approved_revision = next(item for item in revisions_after_approval if item["proposedChunkId"] == proposed_id)
    assert approved_revision["status"] == "approved"
    assert approved_revision["reviewedAt"]
    assert approved_revision["reviewedBy"] == "reviewer-b"
    assert approved_revision["approvedChunkId"] == proposed_id
    assert approved_revision["replacedChunkId"] == chunk_id

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

    revisions = data_store.load_knowledge_revisions()
    rejected_revision = next(item for item in revisions if item["proposedChunkId"] == proposed_id)
    assert rejected_revision["status"] == "rejected"
    assert rejected_revision["reviewedAt"]
    assert rejected_revision["reviewedBy"] == "reviewer-b"
    assert rejected_revision["reviewNote"] == "not grounded"


def test_non_current_chunk_cannot_be_revised(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    client = make_client(tmp_path, monkeypatch)
    document_id, chunk_id = upload_and_approve_chunk(client)
    proposed_id = propose_revision(client, document_id, chunk_id)

    approve_v2 = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "approve", "reviewer": "reviewer-b"},
    )
    assert approve_v2.status_code == 200

    revise_old = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}",
        json={"content": "another stale correction", "reason": "stale", "reviewer": "reviewer-c"},
    )

    assert revise_old.status_code == 409
    assert revise_old.json()["message"] == "Only current approved knowledge chunk can be revised"


def test_duplicate_pending_revision_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    client = make_client(tmp_path, monkeypatch)
    document_id, chunk_id = upload_and_approve_chunk(client)
    propose_revision(client, document_id, chunk_id)

    duplicate = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{chunk_id}",
        json={"content": "duplicate correction", "reason": "duplicate", "reviewer": "reviewer-c"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["message"] == "A pending revision already exists for this knowledge chunk"


def test_stale_revision_proposal_cannot_be_approved(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    client = make_client(tmp_path, monkeypatch)
    document_id, chunk_id = upload_and_approve_chunk(client)
    proposed_id = propose_revision(client, document_id, chunk_id)

    chunks = data_store.load_document_chunks()
    original = next(chunk for chunk in chunks if chunk["id"] == chunk_id)
    original["is_current"] = False
    original["replaced_by"] = "external-current"
    data_store.save_document_chunks(chunks)

    approve = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "approve", "reviewer": "reviewer-b"},
    )

    assert approve.status_code == 409
    assert approve.json()["message"] == "Superseded knowledge chunk is no longer current"
    unchanged = next(chunk for chunk in data_store.load_document_chunks() if chunk["id"] == proposed_id)
    assert unchanged["review_status"] == "pending_review"


def test_revision_proposal_cannot_be_approved_twice(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: None)
    client = make_client(tmp_path, monkeypatch)
    document_id, chunk_id = upload_and_approve_chunk(client)
    proposed_id = propose_revision(client, document_id, chunk_id)

    first = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "approve", "reviewer": "reviewer-b"},
    )
    second = client.patch(
        f"/api/knowledge/documents/{document_id}/chunks/{proposed_id}/review",
        json={"action": "approve", "reviewer": "reviewer-b"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
