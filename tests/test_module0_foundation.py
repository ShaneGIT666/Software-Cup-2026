from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.db.session import database_status, dispose_engine
from backend.app.main import app


def test_v1_live_returns_stable_envelope_and_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "foundation-test-001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "foundation-test-001"
    payload = response.json()
    assert payload == {
        "success": True,
        "data": {
            "status": "ok",
            "service": "repair-knowledge-assistant",
            "apiVersion": "v1",
            "environment": "development",
        },
        "error": None,
        "meta": {"requestId": "foundation-test-001"},
    }


def test_v1_invalid_request_id_is_replaced_safely() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "invalid request id"})

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id != "invalid request id"
    assert response.json()["meta"]["requestId"] == request_id
    assert len(request_id) == 32


def test_v1_not_found_uses_error_contract_and_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/not-found", headers={"X-Request-ID": "foundation-test-404"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "foundation-test-404"
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "HTTP_ERROR"
    assert payload["meta"]["requestId"] == "foundation-test-404"


def test_legacy_health_stays_compatible_and_adds_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/health", headers={"X-Request-ID": "legacy-test-001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "legacy-test-001"
    assert response.json() == {"success": True, "data": {"status": "ok", "version": "0.1.0"}, "message": ""}


def test_ready_is_degraded_but_available_when_database_is_optional(monkeypatch) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    dispose_engine()
    client = TestClient(app)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["database"] == {
        "configured": False,
        "required": False,
        "healthy": False,
        "dialect": None,
        "reason": "APP_DATABASE_URL 未配置",
    }


def test_ready_fails_when_required_database_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "true")
    dispose_engine()
    client = TestClient(app)

    response = client.get("/api/v1/health/ready", headers={"X-Request-ID": "required-db-001"})

    assert response.status_code == 503
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert payload["meta"]["requestId"] == "required-db-001"
    assert payload["error"]["details"]["database"]["required"] is True


def test_database_contract_only_accepts_postgres(monkeypatch) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite:///not-supported.db")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "true")
    dispose_engine()

    settings = get_settings()
    status = database_status(settings)

    assert settings.is_postgres_database is False
    assert status.healthy is False
    assert status.reason == "APP_DATABASE_URL 必须使用 PostgreSQL 连接串"
