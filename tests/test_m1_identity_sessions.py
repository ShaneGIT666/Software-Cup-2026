from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.domains.identity.sessions import (
    issue_session_secrets,
    secret_digest,
    secrets_equal,
    session_is_active,
)


def test_session_issues_only_digests_for_persistence() -> None:
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    issued = issue_session_secrets(
        secret="test-auth-secret",
        ttl_minutes=480,
        idle_timeout_minutes=30,
        now=now,
    )

    assert issued.token != issued.token_digest
    assert issued.csrf_token != issued.csrf_digest
    assert issued.token_digest == secret_digest(issued.token, secret="test-auth-secret")
    assert secrets_equal(issued.csrf_token, issued.csrf_digest, secret="test-auth-secret")
    assert issued.expires_at == now + timedelta(minutes=480)
    assert issued.idle_expires_at == now + timedelta(minutes=30)


def test_session_requires_both_absolute_and_idle_validity() -> None:
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    common = {"expires_at": now + timedelta(hours=1), "idle_expires_at": now + timedelta(minutes=10)}

    assert session_is_active(**common, revoked_at=None, now=now)
    assert not session_is_active(**common, revoked_at=now, now=now)
    assert not session_is_active(
        expires_at=now + timedelta(hours=1),
        idle_expires_at=now,
        revoked_at=None,
        now=now,
    )

