from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from backend.app.core.config import AppSettings
from backend.app.core.errors import AppError
from backend.app.domains.identity.contracts import Permission
from backend.app.domains.identity.dependencies import get_current_user, require_csrf, require_permissions
from backend.app.domains.identity.repository import SessionIdentityRecord
from backend.app.domains.identity.sessions import csrf_token_for_session, secret_digest


NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)
RAW_TOKEN = "session-token-for-tests"


def _settings() -> AppSettings:
    return AppSettings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
        database_required=True,
        application_name="m1-test",
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


def _request(*, csrf: str | None = None) -> Request:
    headers = [(b"cookie", f"repair_session={RAW_TOKEN}".encode("ascii"))]
    if csrf is not None:
        headers.append((b"x-csrf-token", csrf.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/auth/me",
            "raw_path": b"/api/v1/auth/me",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
    )


def _record(settings: AppSettings, *, auth_version: int = 2) -> SessionIdentityRecord:
    csrf = csrf_token_for_session(RAW_TOKEN, secret=settings.auth_secret)
    return SessionIdentityRecord(
        session_id="session-1",
        user_id="user-1",
        session_auth_version=auth_version,
        user_auth_version=2,
        user_is_active=True,
        user_deleted_at=None,
        csrf_digest=secret_digest(
            csrf,
            secret=settings.auth_secret,
            purpose="csrf-token-digest",
        ),
        expires_at=NOW + timedelta(hours=8),
        idle_expires_at=NOW + timedelta(minutes=30),
        revoked_at=None,
        roles=frozenset({"technician"}),
    )


def test_current_user_is_resolved_from_server_session_and_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    repository = Mock()
    repository.resolve_session.return_value = _record(settings)
    repository.refresh_session_activity.return_value = False
    db_session = Mock()
    monkeypatch.setattr("backend.app.domains.identity.dependencies.utc_now", lambda: NOW)

    current_user = get_current_user(_request(), db_session, settings, repository)

    assert current_user.id == "user-1"
    assert current_user.roles == frozenset({"technician"})
    assert Permission.KNOWLEDGE_READ.value in current_user.permissions
    repository.resolve_session.assert_called_once_with(
        db_session,
        secret_digest(RAW_TOKEN, secret=settings.auth_secret),
    )
    db_session.commit.assert_not_called()


def test_auth_version_mismatch_invalidates_existing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    repository = Mock()
    repository.resolve_session.return_value = _record(settings, auth_version=1)
    monkeypatch.setattr("backend.app.domains.identity.dependencies.utc_now", lambda: NOW)

    with pytest.raises(AppError) as exc_info:
        get_current_user(_request(), Mock(), settings, repository)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "SESSION_EXPIRED"
    repository.refresh_session_activity.assert_not_called()


def test_csrf_header_is_bound_to_the_current_session(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    csrf = csrf_token_for_session(RAW_TOKEN, secret=settings.auth_secret)
    request = _request(csrf=csrf)
    repository = Mock()
    repository.resolve_session.return_value = _record(settings)
    repository.refresh_session_activity.return_value = False
    monkeypatch.setattr("backend.app.domains.identity.dependencies.utc_now", lambda: NOW)
    current_user = get_current_user(request, Mock(), settings, repository)

    assert require_csrf(request, current_user, settings) == current_user

    bad_request = _request(csrf="wrong-token")
    bad_user = get_current_user(bad_request, Mock(), settings, repository)
    with pytest.raises(AppError) as exc_info:
        require_csrf(bad_request, bad_user, settings)
    assert exc_info.value.code == "CSRF_INVALID"


def test_permission_dependency_consumes_current_user_contract() -> None:
    dependency = require_permissions(Permission.KNOWLEDGE_READ)
    allowed = Mock(permissions=frozenset({Permission.KNOWLEDGE_READ.value}))
    assert dependency(allowed) is allowed

    denied = Mock(permissions=frozenset())
    with pytest.raises(AppError) as exc_info:
        dependency(denied)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "FORBIDDEN"

