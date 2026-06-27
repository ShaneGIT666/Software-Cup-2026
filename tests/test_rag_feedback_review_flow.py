from __future__ import annotations

import shutil

from fastapi.testclient import TestClient

from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("MINERU_ENABLED", "false")
    monkeypatch.setenv("REMOTE_API_MODE", "off")
    return TestClient(app)


def test_rag_feedback_defaults_to_pending_and_can_be_approved_into_graph(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    create = client.post(
        "/api/rag/feedback",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "maintenanceLevel": "normal_repair",
            "originalAnswer": "旧回答：直接更换总成。",
            "correctedAnswer": "修正：先检查燃油压力和点火系统，再决定是否更换部件。",
            "labels": ["人工修正", "燃油压力"],
            "reason": "原回答缺少检查步骤",
            "reviewer": "operator-a",
        },
    )

    assert create.status_code == 200
    feedback = create.json()["data"]
    assert feedback["status"] == "pending_review"

    pending = client.get("/api/rag/feedback?status=pending_review").json()["data"]
    assert any(item["id"] == feedback["id"] for item in pending["items"])

    graph_before = client.get("/api/knowledge/graph").json()["data"]
    assert f"rag_feedback:{feedback['id']}" not in {node["id"] for node in graph_before["nodes"]}

    approve = client.patch(
        f"/api/rag/feedback/{feedback['id']}/review",
        json={"action": "approve", "reviewer": "reviewer-a", "reviewNote": "修正合理"},
    )

    assert approve.status_code == 200
    assert approve.json()["data"]["status"] == "approved"

    graph_after = client.get("/api/knowledge/graph").json()["data"]
    node_ids = {node["id"] for node in graph_after["nodes"]}
    assert f"rag_feedback:{feedback['id']}" in node_ids
    assert graph_after["approvedOnly"] is True


def test_rejected_and_pending_rag_feedback_do_not_enter_graph(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    pending = client.post(
        "/api/rag/feedback",
        json={
            "deviceModel": "泵站-P1",
            "faultText": "压力波动",
            "originalAnswer": "旧回答",
            "labels": ["待复核"],
            "reviewer": "operator-a",
        },
    ).json()["data"]
    rejected = client.post(
        "/api/rag/feedback",
        json={
            "deviceModel": "泵站-P2",
            "faultText": "异常振动",
            "originalAnswer": "旧回答",
            "reason": "疑似错误",
            "reviewer": "operator-a",
        },
    ).json()["data"]
    reject_response = client.patch(
        f"/api/rag/feedback/{rejected['id']}/review",
        json={"action": "reject", "reviewer": "reviewer-b", "reviewNote": "证据不足"},
    )

    assert reject_response.status_code == 200
    graph = client.get("/api/knowledge/graph").json()["data"]
    node_ids = {node["id"] for node in graph["nodes"]}
    assert f"rag_feedback:{pending['id']}" not in node_ids
    assert f"rag_feedback:{rejected['id']}" not in node_ids


def test_rag_feedback_requires_annotation_content_and_does_not_break_rag(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    invalid = client.post(
        "/api/rag/feedback",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "originalAnswer": "旧回答",
            "correctedAnswer": "",
            "labels": [],
            "reason": "",
        },
    )
    assert invalid.status_code == 400

    rag = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "maintenanceLevel": "normal_repair",
            "riskLevel": "medium",
            "topK": 5,
        },
    )
    assert rag.status_code == 200
    structured = rag.json()["data"]["structuredAnswer"]
    assert "complianceChecks" in structured
