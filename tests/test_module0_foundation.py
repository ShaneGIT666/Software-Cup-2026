from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from unittest.mock import Mock

from backend.app.core.config import get_settings
from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.core.request_context import RequestContextMiddleware
from backend.app.db import session as session_module
from backend.app.db.session import database_status, dispose_engine
from backend.app.main import app, unhandled_exception_handler


@pytest.mark.parametrize("value", ["prodution", "", "   "])
def test_unknown_or_empty_app_environment_fails_closed(monkeypatch, value: str) -> None:
    monkeypatch.setenv("APP_ENV", value)

    with pytest.raises(ValueError, match="APP_ENV"):
        get_settings()


def test_unhandled_v1_exception_returns_sanitized_stable_envelope() -> None:
    isolated_app = FastAPI()
    isolated_app.add_middleware(RequestContextMiddleware)
    isolated_app.add_exception_handler(Exception, unhandled_exception_handler)

    @isolated_app.get("/api/v1/explode")
    def explode() -> None:
        raise RuntimeError("database password=do-not-leak")

    response = TestClient(isolated_app, raise_server_exceptions=False).get(
        "/api/v1/explode",
        headers={"X-Request-ID": "foundation-test-500"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "foundation-test-500"
    payload = response.json()
    assert payload["error"] == {
        "code": ErrorCode.INTERNAL_ERROR,
        "message": "服务器内部错误",
        "details": None,
    }
    assert payload["meta"]["requestId"] == "foundation-test-500"
    assert "do-not-leak" not in response.text


def test_every_v1_operation_declares_the_sanitized_internal_error_contract() -> None:
    schema = app.openapi()
    operations = [
        operation
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1")
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]

    assert operations
    for operation in operations:
        response = operation["responses"]["500"]
        assert response["description"] == "服务器内部错误；响应使用脱敏 v1 错误信封并包含 request ID。"
        schema_ref = response["content"]["application/json"]["schema"]["$ref"]
        assert schema_ref == "#/components/schemas/V1Response"


def test_unhandled_legacy_exception_keeps_legacy_envelope_without_leaking_details() -> None:
    isolated_app = FastAPI()
    isolated_app.add_middleware(RequestContextMiddleware)
    isolated_app.add_exception_handler(Exception, unhandled_exception_handler)

    @isolated_app.get("/api/explode")
    def explode() -> None:
        raise RuntimeError("legacy token=do-not-leak")

    response = TestClient(isolated_app, raise_server_exceptions=False).get(
        "/api/explode",
        headers={"X-Request-ID": "legacy-test-500"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "legacy-test-500"
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "服务器内部错误",
        "requestId": "legacy-test-500",
    }
    assert "do-not-leak" not in response.text


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
    assert payload["data"]["identity"]["required"] is False


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


def test_ready_fails_closed_for_required_identity_configuration(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.delenv("APP_AUTH_SECRET", raising=False)
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")
    dispose_engine()

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 503
    identity = response.json()["error"]["details"]["identity"]
    assert identity == {
        "required": True,
        "healthy": False,
        "mode": "local",
        "reason": "身份认证配置未就绪",
    }


def test_production_database_cannot_be_downgraded_to_optional(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_AUTH_SECRET", "a" * 32)
    monkeypatch.setenv("APP_IDEMPOTENCY_SECRET", "i" * 32)
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com")
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "disabled")
    dispose_engine()

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 503
    database = response.json()["error"]["details"]["database"]
    assert database["required"] is True
    assert database["healthy"] is False


def test_production_foundation_requires_idempotency_secret_and_https_origin(monkeypatch) -> None:
    import backend.app.core.readiness as readiness_module

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_AUTH_SECRET", "a" * 32)
    monkeypatch.delenv("APP_IDEMPOTENCY_SECRET", raising=False)
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")
    monkeypatch.delenv("APP_TRUSTED_ORIGINS", raising=False)
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "disabled")
    monkeypatch.setattr(readiness_module, "database_status", lambda settings: type("Status", (), {
        "healthy": True,
        "reason": "",
        "configured": True,
        "dialect": "postgresql",
    })())
    dispose_engine()

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 503
    foundation = response.json()["error"]["details"]["foundation"]
    assert foundation["required"] is True
    assert foundation["healthy"] is False
    assert set(foundation["violations"]) == {"idempotency_secret", "trusted_https_origins"}


def test_database_contract_only_accepts_postgres(monkeypatch) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", "sqlite:///not-supported.db")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "true")
    dispose_engine()

    settings = get_settings()
    status = database_status(settings)

    assert settings.is_postgres_database is False
    assert status.healthy is False
    assert status.reason == "APP_DATABASE_URL 必须使用 PostgreSQL 连接串"


def test_request_session_maps_missing_database_to_stable_503(monkeypatch) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    dispose_engine()

    dependency = session_module.get_session()
    with pytest.raises(AppError) as exc_info:
        next(dependency)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "DEPENDENCY_UNAVAILABLE"
    assert "APP_DATABASE_URL" not in exc_info.value.message


class _SessionContext:
    def __init__(self, session) -> None:  # type: ignore[no-untyped-def]
        self.session = session

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self.session

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None


def test_new_session_owns_commit_and_rollback(monkeypatch) -> None:
    committed = Mock()
    monkeypatch.setattr(session_module, "_session_factory", lambda: _SessionContext(committed))

    with session_module.new_session() as yielded:
        assert yielded is committed

    committed.commit.assert_called_once()
    committed.rollback.assert_not_called()

    rolled_back = Mock()
    monkeypatch.setattr(session_module, "_session_factory", lambda: _SessionContext(rolled_back))
    with pytest.raises(ValueError, match="business failure"):
        with session_module.new_session():
            raise ValueError("business failure")

    rolled_back.rollback.assert_called_once()
    rolled_back.commit.assert_not_called()


def test_new_session_maps_pool_timeout_to_stable_503(monkeypatch) -> None:
    session = Mock()
    session.commit.side_effect = SQLAlchemyTimeoutError("pool exhausted")
    monkeypatch.setattr(session_module, "_session_factory", lambda: _SessionContext(session))

    with pytest.raises(AppError) as exc_info:
        with session_module.new_session():
            pass

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "DEPENDENCY_UNAVAILABLE"
    assert "pool exhausted" not in exc_info.value.message
    session.rollback.assert_called_once()
