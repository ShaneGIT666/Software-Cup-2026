from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def secret_digest(value: str, *, secret: str) -> str:
    if not secret:
        raise ValueError("会话摘要需要 APP_AUTH_SECRET")
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def secrets_equal(provided_value: str, expected_digest: str, *, secret: str) -> bool:
    return hmac.compare_digest(secret_digest(provided_value, secret=secret), expected_digest)


@dataclass(frozen=True)
class NewSessionSecrets:
    token: str
    token_digest: str
    csrf_token: str
    csrf_digest: str
    expires_at: datetime
    idle_expires_at: datetime


def issue_session_secrets(
    *,
    secret: str,
    ttl_minutes: int,
    idle_timeout_minutes: int,
    now: datetime | None = None,
) -> NewSessionSecrets:
    issued_at = now or utc_now()
    token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    return NewSessionSecrets(
        token=token,
        token_digest=secret_digest(token, secret=secret),
        csrf_token=csrf_token,
        csrf_digest=secret_digest(csrf_token, secret=secret),
        expires_at=issued_at + timedelta(minutes=ttl_minutes),
        idle_expires_at=issued_at + timedelta(minutes=idle_timeout_minutes),
    )


def session_is_active(
    *,
    expires_at: datetime,
    idle_expires_at: datetime,
    revoked_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    checked_at = now or utc_now()
    return revoked_at is None and checked_at < expires_at and checked_at < idle_expires_at

