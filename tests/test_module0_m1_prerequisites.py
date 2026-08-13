from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.api.v1.domain_registry import DOMAIN_ROUTER_MODULES
from backend.app.api.v1.responses import v1_page, v1_success
from backend.app.core.config import get_settings
from backend.app.core.cors import CORS_ALLOWED_HEADERS, cors_middleware_options
from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.db.domain_models import load_domain_models
from backend.app.db.idempotency import request_fingerprint, validate_idempotency_key
from backend.app.main import app


def _request_with_id(request_id: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/users", "headers": []})
    request.state.request_id = request_id
    return request


def test_development_default_cors_is_local_and_explicit(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_TRUSTED_ORIGINS", raising=False)

    settings = get_settings()
    policy = cors_middleware_options(settings)

    assert settings.trusted_origins == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert policy["allow_credentials"] is True
    assert "*" not in policy["allow_origins"]
    assert "*" not in policy["allow_methods"]
    assert "*" not in policy["allow_headers"]
    assert {"Idempotency-Key", "If-Match", "X-CSRF-Token"}.issubset(CORS_ALLOWED_HEADERS)


def test_cors_middleware_accepts_only_the_configured_development_origin() -> None:
    client = TestClient(app)
    headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,idempotency-key,x-csrf-token",
    }

    allowed = client.options("/api/v1/health/live", headers={**headers, "Origin": "http://localhost:5173"})
    rejected = client.options("/api/v1/health/live", headers={**headers, "Origin": "https://untrusted.example.com"})

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_production_cors_fails_closed_when_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_TRUSTED_ORIGINS", raising=False)

    assert get_settings().trusted_origins == ()


def test_trusted_origins_reject_wildcards_and_paths(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com/*")

    with pytest.raises(ValueError, match="APP_TRUSTED_ORIGINS"):
        get_settings()


def test_page_response_uses_the_frozen_cursor_envelope() -> None:
    payload = v1_page(
        _request_with_id("page-contract-001"),
        [{"id": "user-001"}],
        next_cursor="opaque-next-cursor",
    )

    assert payload.dict() == {
        "success": True,
        "data": {"items": [{"id": "user-001"}]},
        "error": None,
        "meta": {"requestId": "page-contract-001", "nextCursor": "opaque-next-cursor"},
    }


def test_success_helper_preserves_non_default_success_status() -> None:
    response = v1_success(_request_with_id("created-contract-001"), {"id": "user-001"}, status_code=201)

    assert response.status_code == 201
    assert response.body == (
        b'{"success":true,"data":{"id":"user-001"},"error":null,'
        b'"meta":{"requestId":"created-contract-001"}}'
    )


def test_domain_router_registry_reserves_m1_without_requiring_it_yet() -> None:
    assert DOMAIN_ROUTER_MODULES[:3] == ("auth", "users", "audit")


def test_domain_model_discovery_is_safe_before_m1_is_delivered() -> None:
    load_domain_models()


def test_m1_model_and_route_contracts_are_referenced_by_m0_discovery() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = (root / "backend" / "app" / "api" / "v1" / "domain_registry.py").read_text(encoding="utf-8")
    model_registry = (root / "backend" / "app" / "db" / "domain_models.py").read_text(encoding="utf-8")

    assert '"auth"' in registry
    assert '"users"' in registry
    assert '"audit"' in registry
    assert '"domains.identity.models"' in model_registry
    assert '"domains.audit.models"' in model_registry


def test_idempotency_key_and_request_fingerprint_contract() -> None:
    key = validate_idempotency_key("create-user:550e8400-e29b-41d4-a716-446655440000")
    first = request_fingerprint(
        actor_id="admin-001",
        method="post",
        path="/api/v1/users",
        payload={"username": "alice", "roles": ["technician"]},
        secret="module0-test-secret",
    )
    equivalent = request_fingerprint(
        actor_id="admin-001",
        method="POST",
        path="/api/v1/users",
        payload={"roles": ["technician"], "username": "alice"},
        secret="module0-test-secret",
    )
    changed = request_fingerprint(
        actor_id="admin-001",
        method="POST",
        path="/api/v1/users",
        payload={"username": "alice", "roles": ["reviewer"]},
        secret="module0-test-secret",
    )

    assert key.startswith("create-user:")
    assert first == equivalent
    assert first != changed


def test_idempotency_fingerprint_requires_a_deployment_secret() -> None:
    with pytest.raises(AppError) as exc_info:
        request_fingerprint(
            actor_id="admin-001",
            method="POST",
            path="/api/v1/users",
            payload={"username": "alice", "password": "not-persisted"},
            secret="",
        )

    assert exc_info.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_invalid_idempotency_key_uses_frozen_error_code() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_idempotency_key("short")

    assert exc_info.value.code == ErrorCode.IDEMPOTENCY_KEY_REQUIRED
