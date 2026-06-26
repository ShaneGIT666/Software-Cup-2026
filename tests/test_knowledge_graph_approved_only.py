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


def test_global_knowledge_graph_excludes_unapproved_chunks_and_cases(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    data_store.save_documents(
        [
            {
                "id": "doc-approved",
                "fileName": "approved-manual.pdf",
                "sourceName": "已审核手册",
                "status": "approved",
                "parser": "mock",
            },
            {
                "id": "doc-pending",
                "fileName": "pending-manual.pdf",
                "sourceName": "待审核手册",
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
                "content": "泵站 P1 出口压力波动时，先检查密封和排气状态。",
                "snippet": "泵站 P1 出口压力波动",
                "review_status": "approved",
                "device_model": "泵站-P1",
                "component": "密封组件",
                "fault_symptom": "压力波动",
                "knowledge_type": "troubleshooting",
                "section": "压力波动",
            },
            {
                "id": "chunk-pending",
                "documentId": "doc-pending",
                "content": "这是一条未审核片段，不应进入关系网络。",
                "snippet": "未审核片段",
                "review_status": "pending_review",
                "device_model": "泵站-P2",
                "component": "未审核部件",
                "fault_symptom": "未审核故障",
                "knowledge_type": "manual_excerpt",
            },
        ]
    )
    data_store.save_cases(
        [
            {
                "id": "case-approved",
                "deviceModel": "泵站-P1",
                "faultText": "压力波动",
                "cause": "密封失效",
                "solution": "复查密封",
                "status": "approved",
                "tags": ["压力波动"],
            },
            {
                "id": "case-pending",
                "deviceModel": "泵站-P2",
                "faultText": "未审核故障",
                "cause": "未知",
                "solution": "未知",
                "status": "pending_review",
                "tags": ["未审核"],
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
    assert "case:case-pending" not in node_ids
    assert "document:doc-pending" not in node_ids
