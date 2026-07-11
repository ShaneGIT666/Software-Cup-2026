from __future__ import annotations

import shutil

from fastapi.testclient import TestClient

import backend.app.data_store as data_store
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("MINERU_ENABLED", "false")
    return TestClient(app)


def test_global_knowledge_graph_excludes_unapproved_unknown_chunks_and_cases(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    data_store.save_documents(
        [
            {
                "id": "doc-approved",
                "fileName": "approved-manual.pdf",
                "sourceName": "Approved manual",
                "status": "approved",
                "parser": "mock",
            },
            {
                "id": "doc-pending",
                "fileName": "pending-manual.pdf",
                "sourceName": "Pending manual",
                "status": "pending_review",
                "parser": "mock",
            },
        ]
    )
    data_store.save_document_chunks(
        [
            {
                "id": "chunk-approved",
                "documentId": "doc-approved",
                "content": "Pump P1 pressure oscillation requires seal and air purge checks.",
                "snippet": "Pump P1 pressure oscillation",
                "review_status": "approved",
                "is_current": True,
                "device_model": "PUMP-P1",
                "component": "seal",
                "fault_symptom": "pressure oscillation",
                "knowledge_type": "troubleshooting",
                "section": "pressure",
            },
            {
                "id": "chunk-pending",
                "documentId": "doc-pending",
                "content": "Pending chunk must not enter the graph.",
                "snippet": "Pending chunk",
                "review_status": "pending_review",
                "device_model": "PUMP-P2",
                "component": "pending",
                "fault_symptom": "pending",
                "knowledge_type": "manual_excerpt",
            },
            {
                "id": "chunk-missing-status",
                "documentId": "doc-approved",
                "content": "Missing review status must be treated as unknown.",
                "snippet": "Missing review status",
                "device_model": "PUMP-P3",
                "component": "unknown",
                "fault_symptom": "unknown",
                "knowledge_type": "manual_excerpt",
            },
        ]
    )
    data_store.save_cases(
        [
            {
                "id": "case-approved",
                "faultTitle": "pressure oscillation",
                "deviceModel": "PUMP-P1",
                "faultText": "pressure oscillation",
                "cause": "seal failure",
                "solution": "inspect seal",
                "status": "approved",
                "tags": ["pressure"],
            },
            {
                "id": "case-pending",
                "faultTitle": "pending case",
                "deviceModel": "PUMP-P2",
                "faultText": "pending",
                "cause": "unknown",
                "solution": "unknown",
                "status": "pending_review",
                "tags": ["pending"],
            },
            {
                "id": "case-missing-status",
                "faultTitle": "missing status case",
                "deviceModel": "PUMP-P3",
                "faultText": "missing",
                "cause": "unknown",
                "solution": "unknown",
                "tags": ["unknown"],
            },
        ]
    )

    response = client.get("/api/knowledge/graph")

    assert response.status_code == 200
    graph = response.json()["data"]
    node_ids = {node["id"] for node in graph["nodes"]}
    assert graph["approvedOnly"] is True
    assert "chunk:chunk-approved" in node_ids
    assert "case:case-approved" in node_ids
    assert "document:doc-approved" in node_ids
    assert "chunk:chunk-pending" not in node_ids
    assert "chunk:chunk-missing-status" not in node_ids
    assert "case:case-pending" not in node_ids
    assert "case:case-missing-status" not in node_ids
    assert "document:doc-pending" not in node_ids
