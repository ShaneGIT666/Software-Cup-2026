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
    return TestClient(app)


def test_case_experience_fields_default_to_pending_review_and_survive_approval(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    create_response = client.post(
        "/api/cases",
        json={
            "deviceModel": "compressor-C2",
            "faultText": "coupling vibration increased",
            "cause": "coupling offset",
            "solution": "realign coupling and recheck base bolts",
            "result": "vibration returned to allowed range",
            "experienceSummary": "vibration fault should check coupling alignment first",
            "lessonsLearned": "retest must include no-load and loaded states",
            "maintenanceLevel": "major_repair",
            "tags": ["振动", "联轴器"],
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["status"] == "pending_review"
    assert created["experienceSummary"] == "vibration fault should check coupling alignment first"
    assert created["lessonsLearned"] == "retest must include no-load and loaded states"
    assert created["maintenanceLevel"] == "major_repair"

    search_before = client.post(
        "/api/search",
        json={"deviceModel": "compressor-C2", "faultText": "coupling alignment", "topK": 5},
    ).json()["data"]["results"]
    assert all(item["id"] != created["id"] for item in search_before)

    approve_response = client.patch(
        f"/api/cases/{created['id']}/review",
            json={"action": "approve", "reviewer": "reviewer-a", "reviewNote": "experience complete"},
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()["data"]
    assert approved["status"] == "approved"
    assert approved["maintenanceLevel"] == "major_repair"

    search_after = client.post(
        "/api/search",
        json={"deviceModel": "compressor-C2", "faultText": "coupling alignment", "topK": 5},
    ).json()["data"]["results"]
    assert any(item["id"] == created["id"] and item["sourceType"] == "case" for item in search_after)


def test_rejected_experience_case_is_not_searchable(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    created = client.post(
        "/api/cases",
        json={
            "deviceModel": "pump-P1",
            "faultText": "outlet pressure oscillation",
            "cause": "suspected air in pipeline",
            "solution": "vent air and recheck sealing",
            "result": "pending verification",
            "experienceSummary": "unverified field note",
            "lessonsLearned": "insufficient evidence",
            "maintenanceLevel": "normal_repair",
            "tags": ["pressure oscillation"],
        },
    ).json()["data"]

    reject_response = client.patch(
        f"/api/cases/{created['id']}/review",
        json={"action": "reject", "reviewer": "reviewer-b", "reviewNote": "missing retest record"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "rejected"

    results = client.post(
        "/api/search",
        json={"deviceModel": "pump-P1", "faultText": "pressure oscillation vent air", "topK": 5},
    ).json()["data"]["results"]
    assert all(item["id"] != created["id"] for item in results)
