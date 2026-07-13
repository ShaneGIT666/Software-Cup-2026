from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


MANAGEMENT_GET_ENDPOINTS = (
    "/api/providers/status",
    "/api/knowledge/documents",
    "/api/knowledge/parse-tasks",
    "/api/review/items?status=pending_review",
    "/api/cases",
    "/api/knowledge/graph",
    "/api/review/events?limit=100",
)


def configure_off(monkeypatch, *, app_env: str = "development", allow: str = "true") -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ALLOW_INSECURE_AUTH_OFF", allow)


def configure_tokens(monkeypatch) -> dict[str, str]:
    tokens = {
        "operator": "runtime-test-operator",
        "reviewer": "runtime-test-reviewer",
        "admin": "runtime-test-admin",
    }
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.setenv("ALLOW_INSECURE_AUTH_OFF", "false")
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setenv("AUTH_OPERATOR_TOKEN", tokens["operator"])
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", tokens["reviewer"])
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", tokens["admin"])
    return tokens


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_development_off_mode_allows_all_management_reads_without_token(monkeypatch) -> None:
    configure_off(monkeypatch)
    client = TestClient(app)

    responses = [client.get(endpoint) for endpoint in MANAGEMENT_GET_ENDPOINTS]

    assert [response.status_code for response in responses] == [200] * len(MANAGEMENT_GET_ENDPOINTS)
    auth = responses[0].json()["data"]["system"]["auth"]
    assert auth["mode"] == "off"
    assert auth["valid"] is True
    assert auth["errors"] == []


def test_invalid_development_off_mode_keeps_status_public_and_returns_actionable_503(monkeypatch) -> None:
    configure_off(monkeypatch, allow="false")
    client = TestClient(app)

    status_response = client.get("/api/providers/status")
    protected_response = client.get("/api/knowledge/documents")

    assert status_response.status_code == 200
    auth = status_response.json()["data"]["system"]["auth"]
    assert auth["valid"] is False
    assert auth["errors"] == [
        "认证配置无效：本地开发使用 AUTH_MODE=off 时必须设置 ALLOW_INSECURE_AUTH_OFF=true。"
    ]
    assert protected_response.status_code == 503
    message = protected_response.json()["message"]
    assert message == auth["errors"][0]
    assert "runtime-test" not in message
    assert "\\" not in message


def test_protected_environments_never_allow_off_mode(monkeypatch) -> None:
    for app_env in ("competition", "submission", "production"):
        configure_off(monkeypatch, app_env=app_env, allow="true")
        response = TestClient(app).get("/api/knowledge/documents")
        assert response.status_code == 503
        assert response.json()["message"] == (
            "认证配置无效：competition、submission 和 production 环境必须使用 AUTH_MODE=token。"
        )


def test_token_mode_requires_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "token")
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.delenv("AUTH_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("AUTH_REVIEWER_TOKEN", "runtime-test-reviewer")

    response = TestClient(app).get("/api/knowledge/documents")

    assert response.status_code == 503
    assert response.json()["message"] == "认证配置无效：AUTH_MODE=token 必须配置管理员令牌。"


def test_token_mode_preserves_role_permissions(monkeypatch) -> None:
    tokens = configure_tokens(monkeypatch)
    client = TestClient(app)

    assert client.get("/api/knowledge/documents").status_code == 401
    assert client.get(
        "/api/knowledge/documents", headers=auth_header(tokens["operator"])
    ).status_code == 403
    assert client.get(
        "/api/knowledge/documents", headers=auth_header(tokens["reviewer"])
    ).status_code == 200
    assert client.get(
        "/api/review/items", headers=auth_header(tokens["reviewer"])
    ).status_code == 200

    for endpoint in MANAGEMENT_GET_ENDPOINTS[1:]:
        assert client.get(endpoint, headers=auth_header(tokens["admin"])).status_code == 200

