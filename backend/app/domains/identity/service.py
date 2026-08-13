from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ...core.config import AppSettings
from .models import User
from .passwords import Argon2PasswordHasher, PasswordHasherPort
from .repository import (
    IdentityRepository,
    LoginThrottleRepository,
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
    user: User | None
    subject_hmac: str
    source_hmac: str
    locked: bool

    @property
    def authenticated(self) -> bool:
        return self.user is not None and not self.locked


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
        session: Session,
        *,
        username: str,
        password: str,
        source_address: str,
        settings: AppSettings,
        now: datetime,
    ) -> LoginVerification:
        throttle_subject, normalized_username = self._throttle_subject(username)
        subject_hmac, source_hmac = login_throttle_digests(
            normalized_username=throttle_subject,
            source_address=source_address,
            secret=settings.auth_secret,
        )
        throttle_state = self.throttles.get_state(
            session,
            subject_hmac=subject_hmac,
            source_hmac=source_hmac,
        )
        locked = throttle_state.is_locked(now) if throttle_state else False
        user = (
            self.repository.find_local_user_for_login(session, normalized_username)
            if normalized_username is not None
            else None
        )
        candidate_hash = user.password_hash if user is not None and user.password_hash else _DUMMY_PASSWORD_HASH
        verified = self.password_hasher.verify(candidate_hash, password)
        if user is None or not user.is_active or user.deleted_at is not None or not verified or locked:
            user = None
        return LoginVerification(
            user=user,
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
    ) -> LoginThrottleState:
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
        if not verification.authenticated or verification.user is None:
            raise ValueError("只有成功的凭据验证才能创建会话")
        secrets = issue_session_secrets(
            secret=settings.auth_secret,
            ttl_minutes=settings.session_ttl_minutes,
            idle_timeout_minutes=settings.session_idle_timeout_minutes,
            now=now,
        )
        record = self.repository.create_session(
            session,
            user_id=verification.user.id,
            auth_version=verification.user.auth_version,
            secrets=secrets,
            now=now,
        )
        self.throttles.clear(
            session,
            subject_hmac=verification.subject_hmac,
            source_hmac=verification.source_hmac,
        )
        return CreatedSession(session_id=record.id, secrets=secrets)

