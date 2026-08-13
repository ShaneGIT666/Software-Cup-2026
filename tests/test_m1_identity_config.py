from __future__ import annotations

import pytest

from backend.app.core.config import get_settings


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


def test_production_requires_secret_and_host_cookie(monkeypatch) -> None:
    _clear_auth_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValueError, match="APP_AUTH_SECRET"):
        get_settings()

    monkeypatch.setenv("APP_AUTH_SECRET", "production-auth-secret")
    settings = get_settings()

    assert settings.session_cookie_name == "__Host-repair_session"
    assert settings.session_cookie_secure is True


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

