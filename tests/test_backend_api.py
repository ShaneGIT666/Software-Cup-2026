from __future__ import annotations

import json
import shutil

from fastapi.testclient import TestClient

from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    return TestClient(app)


def test_health(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"


def test_search_returns_seed_results(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/search",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难 怠速不稳",
            "inputType": "text",
            "topK": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["results"]


def test_workflow_lookup(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/api/workflows/wf-001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["id"] == "wf-001"


def test_upload_uses_configured_upload_dir(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("APP_UPLOAD_DIR", str(upload_dir))

    response = client.post(
        "/api/uploads",
        files={"file": ("fault-image.jpg", b"fake image bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["fileName"] == "fault-image.jpg"
    assert (upload_dir / f"{payload['data']['id']}.jpg").exists()


def test_case_submit_review_and_search_round_trip(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    create_response = client.post(
        "/api/cases",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "热机后偶发熄火，怠速控制异常",
            "cause": "怠速控制阀积碳",
            "solution": "清洁怠速控制阀并复测怠速稳定性",
            "result": "热机后未再熄火",
            "tags": ["偶发熄火", "怠速控制"],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["status"] == "pending_review"

    pending_response = client.get("/api/cases?status=pending_review")
    pending_items = pending_response.json()["data"]["items"]
    assert any(item["id"] == created["id"] for item in pending_items)

    review_response = client.patch(
        f"/api/cases/{created['id']}/review",
        json={
            "action": "approve",
            "reviewNote": "内容完整，可入库",
            "normalizedTags": ["偶发熄火", "怠速控制", "发动机"],
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "approved"

    search_response = client.post(
        "/api/search",
        json={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "偶发熄火 怠速控制",
            "inputType": "text",
            "topK": 5,
        },
    )
    results = search_response.json()["data"]["results"]
    assert any(item["id"] == created["id"] and item["sourceType"] == "case" for item in results)

    cases_file = tmp_path / "source" / "repair-cases.json"
    saved_cases = json.loads(cases_file.read_text(encoding="utf-8"))
    saved_case = next(item for item in saved_cases if item["id"] == created["id"])
    assert saved_case["status"] == "approved"
    assert saved_case["reviewedAt"]
