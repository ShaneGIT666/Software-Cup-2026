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


def test_chunk_revision_records_revision_event_and_resyncs_index(tmp_path, monkeypatch) -> None:
    sync_calls: list[list[dict[str, Any]]] = []
    deleted_documents: list[str] = []
    monkeypatch.setattr(knowledge, "sync_chunks", lambda chunks: sync_calls.append(chunks))
    monkeypatch.setattr(knowledge, "delete_vector_document", lambda document_id: deleted_documents.append(document_id))
    client = make_client(tmp_path, monkeypatch)

    upload = client.post(
        "/api/knowledge/documents",
        files={"file": ("field-note.txt", b"old pressure note", "text/plain")},
        data={"source_name": "现场记录"},
    ).json()["data"]
    chunk_id = upload["chunks"][0]["id"]

    revision_response = client.patch(
        f"/api/knowledge/documents/{upload['id']}/chunks/{chunk_id}",
        json={
            "content": "修正后：出口压力波动时先执行排气，再复核密封组件。",
            "tags": ["人工修正", "压力波动"],
            "reason": "一线复盘修正",
            "reviewer": "reviewer-a",
        },
    )

    assert revision_response.status_code == 200
    payload = revision_response.json()["data"]
    assert payload["revision"]["reviewer"] == "reviewer-a"
    assert payload["chunk"]["manuallyCorrected"] is True
    assert deleted_documents == [upload["id"]]
    assert sync_calls and sync_calls[-1][0]["id"] == chunk_id

    events = data_store.load_review_events()
    assert events[-1]["objectType"] == "knowledge_revision"
    assert events[-1]["objectId"] == payload["revision"]["id"]
    assert events[-1]["revisionId"] == payload["revision"]["id"]
    assert events[-1]["reviewer"] == "reviewer-a"
