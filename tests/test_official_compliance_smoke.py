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


def test_official_main_chain_smoke_covers_search_rag_review_graph_and_provider_status(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    health = client.get("/api/health")
    assert health.status_code == 200
    provider = client.get("/api/providers/status").json()["data"]
    assert "llm" in provider
    assert "ocr" in provider
    assert "system" in provider

    search = client.post(
        "/api/search",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "maintenanceLevel": "normal_repair",
            "topK": 5,
        },
    )
    assert search.status_code == 200
    assert "results" in search.json()["data"]

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
    rag_data = rag.json()["data"]
    assert "structuredAnswer" in rag_data
    assert "complianceChecks" in rag_data["structuredAnswer"]

    case = client.post(
        "/api/cases",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "cause": "点火系统积碳",
            "solution": "清洁并复测",
            "result": "启动恢复",
            "experienceSummary": "点火系统积碳会导致启动困难。",
            "lessonsLearned": "复测要记录启动时间。",
            "maintenanceLevel": "normal_repair",
            "tags": ["启动困难"],
        },
    ).json()["data"]
    assert case["status"] == "pending_review"

    review_items = client.get("/api/review/items?status=pending_review").json()["data"]
    assert review_items["total"] >= 1

    graph = client.get("/api/knowledge/graph")
    assert graph.status_code == 200
    assert graph.json()["data"]["approvedOnly"] is True
