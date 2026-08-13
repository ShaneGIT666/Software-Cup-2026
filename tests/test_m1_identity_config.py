from __future__ import annotations

import pytest

from backend.app.core.config import get_settings
from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.domains.identity.runtime import validate_identity_runtime_settings


def _clear_auth_environment(monkeypatch) -> None:
    for name in (
        "APP_AUTH_MODE",
        "APP_AUTH_SECRET",
        "APP_SESSION_COOKIE_NAME",
        "APP_SESSION_COOKIE_SECURE",
        "APP_SESSION_TTL_MINUTES",
        "APP_SESSION_IDLE_TIMEOUT_MINUTES",
        "APP_AUTH_MAX_LOGIN_FAILURES",
        "APP_AUTH_LOGIN_WINDOW_SECONDS",
        "APP_AUTH_LOCK_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_development_auth_defaults_are_local_http_safe(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "development")

    settings = get_settings()

    assert settings.auth_mode == "local"
    assert settings.session_cookie_name == "repair_session"
    assert settings.session_cookie_secure is False
    assert settings.session_ttl_minutes == 480
    assert settings.session_idle_timeout_minutes == 30


def test_production_foundation_uses_host_cookie_before_identity_routes_exist(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")

    settings = get_settings()

    assert settings.session_cookie_name == "__Host-repair_session"
    assert settings.session_cookie_secure is True
    with pytest.raises(AppError) as exc_info:
        validate_identity_runtime_settings(settings)
    assert exc_info.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE

    monkeypatch.setenv("APP_AUTH_SECRET", "production-auth-secret-at-least-32-bytes")
    validate_identity_runtime_settings(get_settings())


def test_host_cookie_prefix_cannot_be_used_without_secure(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "false")

    with pytest.raises(ValueError, match="__Host-"):
        get_settings()


def test_auth_mode_and_numeric_settings_are_validated(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_AUTH_MODE", "fallback")
    with pytest.raises(ValueError, match="APP_AUTH_MODE"):
        get_settings()

    monkeypatch.setenv("APP_AUTH_MODE", "local")
    monkeypatch.setenv("APP_AUTH_MAX_LOGIN_FAILURES", "zero")
    with pytest.raises(ValueError, match="APP_AUTH_MAX_LOGIN_FAILURES"):
        get_settings()


def test_oidc_stays_unavailable_until_m1_1_is_delivered(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_AUTH_MODE", "oidc")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-auth-secret")

    with pytest.raises(AppError) as exc_info:
        validate_identity_runtime_settings(get_settings())
    assert exc_info.value.code == ErrorCode.AUTH_MODE_UNAVAILABLE


def test_identity_runtime_rejects_short_auth_secret(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_AUTH_MODE", "local")
    monkeypatch.setenv("APP_AUTH_SECRET", "too-short")

    with pytest.raises(AppError) as exc_info:
        validate_identity_runtime_settings(get_settings())
    assert exc_info.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert "32 字节" in exc_info.value.message
