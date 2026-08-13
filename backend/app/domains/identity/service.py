from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ...core.config import AppSettings
from .passwords import Argon2PasswordHasher, PasswordHasherPort
from .repository import (
    IdentityRepository,
    LoginCredentialRecord,
    LoginThrottleRepository,
    LoginThrottleSnapshot,
    LoginThrottleState,
    login_throttle_digests,
)
from .sessions import NewSessionSecrets, issue_session_secrets
from .usernames import normalize_username


# A public, non-account hash keeps nonexistent/disabled/invalid-name checks on
# the same expensive Argon2id path as valid local accounts.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$0ehGz1DRPGeWwXZVaFTW4A$"
    "MfZa4yRIk2Qua3veuxuGoufJbW9MX3YSf1Uc0OvQe9o"
)


@dataclass(frozen=True)
class LoginVerification:
    user_id: str | None
    password_hash: str | None
    auth_version: int | None
    subject_hmac: str
    source_hmac: str
    locked: bool

    @property
    def authenticated(self) -> bool:
        return self.user_id is not None and self.password_hash is not None and self.auth_version is not None and not self.locked


@dataclass(frozen=True)
class CreatedSession:
    session_id: str
    secrets: NewSessionSecrets


class IdentityService:
    """Authentication orchestration without owning transaction commits."""

    def __init__(
        self,
        *,
        repository: IdentityRepository | None = None,
        throttle_repository: LoginThrottleRepository | None = None,
        password_hasher: PasswordHasherPort | None = None,
    ) -> None:
        self.repository = repository or IdentityRepository()
        self.throttles = throttle_repository or LoginThrottleRepository()
        self.password_hasher = password_hasher or Argon2PasswordHasher()

    @staticmethod
    def _throttle_subject(username: str) -> tuple[str, str | None]:
        try:
            normalized = normalize_username(username)
            return normalized, normalized
        except ValueError:
            # Preserve a bounded, non-persisted canonical subject solely for
            # HMAC throttling; invalid input must not skip rate limiting.
            fallback = unicodedata.normalize("NFKC", username[:256]).strip().casefold()
            return f"invalid:{fallback}", None

    def verify_login_candidate(
        self,
        *,
        username: str,
        password: str,
        source_address: str,
        settings: AppSettings,
        now: datetime,
        credential: LoginCredentialRecord | None,
        throttle_snapshot: LoginThrottleSnapshot,
    ) -> LoginVerification:
        throttle_subject, normalized_username = self._throttle_subject(username)
        subject_hmac, source_hmac = login_throttle_digests(
            normalized_username=throttle_subject,
            source_address=source_address,
            secret=settings.auth_secret,
        )
        locked = throttle_snapshot.is_locked(now)
        candidate_hash = credential.password_hash if credential is not None else _DUMMY_PASSWORD_HASH
        verified = self.password_hasher.verify(candidate_hash, password)
        accepted = (
            credential is not None
            and credential.is_active
            and credential.deleted_at is None
            and verified
            and not locked
        )
        return LoginVerification(
            user_id=credential.user_id if accepted and credential is not None else None,
            password_hash=credential.password_hash if accepted and credential is not None else None,
            auth_version=credential.auth_version if accepted and credential is not None else None,
            subject_hmac=subject_hmac,
            source_hmac=source_hmac,
            locked=locked,
        )

    def record_failed_login(
        self,
        session: Session,
        *,
        verification: LoginVerification,
        settings: AppSettings,
        now: datetime,
    ) -> LoginThrottleSnapshot:
        return self.throttles.record_failure(
            session,
            subject_hmac=verification.subject_hmac,
            source_hmac=verification.source_hmac,
            now=now,
            max_failures=settings.auth_max_login_failures,
            window_seconds=settings.auth_login_window_seconds,
            lock_seconds=settings.auth_lock_seconds,
        )

    def create_authenticated_session(
        self,
        session: Session,
        *,
        verification: LoginVerification,
        settings: AppSettings,
        now: datetime,
    ) -> CreatedSession:
        if not verification.authenticated:
            raise ValueError("只有成功的凭据验证才能创建会话")
        assert verification.user_id is not None
        assert verification.password_hash is not None
        assert verification.auth_version is not None
        throttle_snapshot = self.throttles.get_states(
            session,
            subject_hmac=verification.subject_hmac,
            source_hmac=verification.source_hmac,
        )
        if throttle_snapshot.is_locked(now):
            raise ValueError("凭据验证后登录限流状态已变化")
        user = self.repository.revalidate_login_candidate(
            session,
            user_id=verification.user_id,
            password_hash=verification.password_hash,
            auth_version=verification.auth_version,
        )
        if user is None:
            raise ValueError("凭据验证后账号安全状态已变化")
        secrets = issue_session_secrets(
            secret=settings.auth_secret,
            ttl_minutes=settings.session_ttl_minutes,
            idle_timeout_minutes=settings.session_idle_timeout_minutes,
            now=now,
        )
        record = self.repository.create_session(
            session,
            user_id=user.id,
            auth_version=user.auth_version,
            secrets=secrets,
            now=now,
        )
        self.throttles.clear_subject(
            session,
            subject_hmac=verification.subject_hmac,
        )
        return CreatedSession(session_id=record.id, secrets=secrets)
