from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hmac_bytes(value: str, *, secret: str, purpose: str) -> bytes:
    if not secret:
        raise ValueError("会话摘要需要 APP_AUTH_SECRET")
    message = f"{purpose}\0{value}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def secret_digest(value: str, *, secret: str, purpose: str = "session-token") -> str:
    return _hmac_bytes(value, secret=secret, purpose=purpose).hex()


def csrf_token_for_session(session_token: str, *, secret: str) -> str:
    """Derive a stable CSRF token without storing its plaintext in the database."""

    raw = _hmac_bytes(session_token, secret=secret, purpose="csrf-token")
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def secrets_equal(
    provided_value: str,
    expected_digest: str,
    *,
    secret: str,
    purpose: str = "csrf-token-digest",
) -> bool:
    actual_digest = secret_digest(provided_value, secret=secret, purpose=purpose)
    return hmac.compare_digest(actual_digest, expected_digest)


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
    csrf_token = csrf_token_for_session(token, secret=secret)
    return NewSessionSecrets(
        token=token,
        token_digest=secret_digest(token, secret=secret),
        csrf_token=csrf_token,
        csrf_digest=secret_digest(csrf_token, secret=secret, purpose="csrf-token-digest"),
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
