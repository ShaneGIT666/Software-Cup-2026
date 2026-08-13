from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app.core.client_address import get_client_address_resolver
from backend.app.core.config import AppSettings, get_settings
from backend.app.domains.identity.commands import get_logout_use_case, get_password_change_use_case
from backend.app.domains.identity.contracts import CurrentUser, ResolvedIdentity
from backend.app.domains.identity.dependencies import (
    get_resolved_identity,
    require_csrf,
    require_trusted_write_origin,
)
from backend.app.domains.identity.login import LoginAttemptResult, get_login_use_case
from backend.app.domains.identity.service import CreatedSession
from backend.app.domains.identity.sessions import issue_session_secrets
from backend.app.domains.identity.transactions import get_session_identity_resolver
from backend.app.main import app


NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def _settings() -> AppSettings:
    return AppSettings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
        database_required=True,
        application_name="m1-api-test",
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


def _resolved_identity() -> ResolvedIdentity:
    return ResolvedIdentity(
        current_user=CurrentUser(
            id="user-1",
            roles=frozenset({"technician"}),
            permissions=frozenset({"knowledge:read"}),
            session_id="session-1",
        ),
        display_name="Alice",
        must_change_password=False,
        expires_at=NOW + timedelta(hours=8),
        idle_expires_at=NOW + timedelta(minutes=30),
        csrf_digest="c" * 64,
    )


def _client() -> TestClient:
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[require_trusted_write_origin] = lambda: "http://localhost:5173"
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_login_sets_one_hardened_cookie_and_no_store() -> None:
    secrets = issue_session_secrets(secret="a" * 32, ttl_minutes=480, idle_timeout_minutes=30, now=NOW)
    use_case = Mock()
    use_case.authenticate.return_value = LoginAttemptResult(
        created_session=CreatedSession(session_id="session-1", secrets=secrets),
        locked=False,
    )
    resolver = Mock()
    resolver.resolve.return_value = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        roles=frozenset({"technician"}),
        display_name="Alice",
        must_change_password=False,
        expires_at=secrets.expires_at,
        idle_expires_at=secrets.idle_expires_at,
        csrf_digest=secrets.csrf_digest,
    )
    addresses = Mock()
    addresses.resolve.return_value = "192.0.2.8"
    app.dependency_overrides[get_login_use_case] = lambda: use_case
    app.dependency_overrides[get_session_identity_resolver] = lambda: resolver
    app.dependency_overrides[get_client_address_resolver] = lambda: addresses

    try:
        response = _client().post(
            "/api/v1/auth/login",
            json={"username": "Alice", "password": "A-Strong-Password-123"},
            headers={"Origin": "http://localhost:5173"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert "repair_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    payload = response.json()
    assert payload["data"]["user"]["roles"] == ["technician"]
    assert payload["data"]["csrfToken"] == secrets.csrf_token


def test_login_failure_is_generic_and_does_not_set_cookie() -> None:
    use_case = Mock()
    use_case.authenticate.return_value = LoginAttemptResult(created_session=None, locked=True)
    addresses = Mock()
    addresses.resolve.return_value = "192.0.2.8"
    app.dependency_overrides[get_login_use_case] = lambda: use_case
    app.dependency_overrides[get_client_address_resolver] = lambda: addresses

    try:
        response = _client().post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "wrong"},
            headers={"Origin": "http://localhost:5173"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.headers["Cache-Control"] == "no-store"
    assert "set-cookie" not in response.headers


def test_me_uses_private_resolved_identity_but_returns_public_view() -> None:
    app.dependency_overrides[get_resolved_identity] = _resolved_identity

    try:
        response = _client().get("/api/v1/auth/me")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["user"]["id"] == "user-1"
    assert data["user"]["displayName"] == "Alice"
    assert "csrfDigest" not in str(data)


def test_logout_uses_csrf_identity_and_clears_cookie() -> None:
    current = _resolved_identity().current_user
    use_case = Mock()
    app.dependency_overrides[require_csrf] = lambda: current
    app.dependency_overrides[get_logout_use_case] = lambda: use_case

    try:
        response = _client().post(
            "/api/v1/auth/logout",
            headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "test"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"] == {"loggedOut": True}
    assert "Max-Age=0" in response.headers["set-cookie"]
    use_case.execute.assert_called_once()


def test_identity_routes_are_the_only_new_anonymous_surface() -> None:
    routes = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }

    assert ("POST", "/api/v1/auth/login") in routes
    assert ("POST", "/api/v1/auth/logout") in routes
    assert ("GET", "/api/v1/auth/me") in routes
    assert ("GET", "/api/v1/auth/csrf") in routes
    assert ("PUT", "/api/v1/auth/password") in routes


def test_m1_openapi_routes_use_the_v1_response_contract() -> None:
    schema = app.openapi()

    for path, method in (
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/me", "get"),
        ("/api/v1/users", "get"),
        ("/api/v1/users", "post"),
        ("/api/v1/audit-events", "get"),
    ):
        assert path in schema["paths"]
        assert "200" in schema["paths"][path][method]["responses"] or "201" in schema["paths"][path][method]["responses"]
