from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"


def test_search_returns_seed_results() -> None:
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


def test_workflow_lookup() -> None:
    response = client.get("/api/workflows/wf-001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["id"] == "wf-001"
