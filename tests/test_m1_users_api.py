from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings, get_settings
from backend.app.domains.identity.admin import WriteResult, get_user_management_use_case
from backend.app.domains.identity.contracts import CurrentUser
from backend.app.domains.identity.dependencies import (
    require_csrf,
    require_permissions,
    require_trusted_write_origin,
)
from backend.app.main import app


ADMIN = CurrentUser(
    id="admin-1",
    roles=frozenset({"system_admin"}),
    permissions=frozenset({"iam:users:read", "iam:users:write", "iam:roles:write"}),
    session_id="session-admin",
)


def _settings() -> AppSettings:
    return AppSettings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
        database_required=True,
        application_name="m1-users-api-test",
        trusted_origins=("http://localhost:5173",),
        idempotency_secret="i" * 32,
        auth_mode="local",
        auth_secret="a" * 32,
        session_cookie_name="repair_session",
        session_cookie_secure=False,
        session_ttl_minutes=480,
        session_idle_timeout_minutes=30,
        auth_max_login_failures=5,
        auth_login_window_seconds=900,
        auth_lock_seconds=900,
    )


def _override_admin(use_case: Mock) -> TestClient:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[require_csrf] = lambda: ADMIN
    app.dependency_overrides[require_trusted_write_origin] = lambda: "http://localhost:5173"
    app.dependency_overrides[get_user_management_use_case] = lambda: use_case
    # Permission factories return stable dependency functions at route declaration;
    # override the CurrentUser source they consume instead of replacing the factory.
    from backend.app.domains.identity.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: ADMIN
    return TestClient(app)


def test_create_user_preserves_v1_etag_idempotency_and_no_store() -> None:
    use_case = Mock()
    use_case.create_user.return_value = WriteResult(
        data={"id": "user-2", "version": 1, "roles": ["technician"]},
        status_code=201,
        version=1,
    )
    client = _override_admin(use_case)

    try:
        response = client.post(
            "/api/v1/users",
            json={
                "username": "alice",
                "displayName": "Alice",
                "initialPassword": "A-Strong-Password-123",
                "roles": ["technician"],
            },
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": "test",
                "Idempotency-Key": "create-user-001",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.headers["ETag"] == '"v1"'
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["id"] == "user-2"
    use_case.create_user.assert_called_once()


def test_role_update_forwards_if_match_and_server_identity() -> None:
    use_case = Mock()
    use_case.set_roles.return_value = WriteResult(
        data={"id": "user-2", "version": 3, "roles": ["reviewer"]},
        status_code=200,
        version=3,
    )
    client = _override_admin(use_case)

    try:
        response = client.put(
            "/api/v1/users/user-2/roles",
            json={"roles": ["reviewer"], "reason": "岗位调整"},
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": "test",
                "If-Match": '"v2"',
                "Idempotency-Key": "roles-change-001",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["ETag"] == '"v3"'
    kwargs = use_case.set_roles.call_args.kwargs
    assert kwargs["current_user"] == ADMIN
    assert kwargs["if_match"] == '"v2"'
    assert kwargs["role_codes"] == ["reviewer"]


def test_roles_endpoint_uses_frozen_server_matrix() -> None:
    use_case = Mock()
    client = _override_admin(use_case)

    try:
        response = client.get("/api/v1/roles")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    roles = {item["code"]: item["permissions"] for item in response.json()["data"]}
    assert "knowledge:review" not in roles["system_admin"]
    assert roles["auditor"] == ["audit:read", "ops:read"]

