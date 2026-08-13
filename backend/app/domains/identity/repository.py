from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import AuthSession, LoginThrottle, Role, User, UserRole
from .sessions import NewSessionSecrets, secret_digest


SESSION_ACTIVITY_REFRESH_SECONDS = 300


@dataclass(frozen=True)
class SessionIdentityRecord:
    session_id: str
    user_id: str
    session_auth_version: int
    user_auth_version: int
    user_is_active: bool
    user_deleted_at: datetime | None
    csrf_digest: str
    expires_at: datetime
    idle_expires_at: datetime
    revoked_at: datetime | None
    roles: frozenset[str]


@dataclass(frozen=True)
class LoginThrottleState:
    failure_count: int
    locked_until: datetime | None

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now


def login_throttle_digests(
    *,
    normalized_username: str,
    source_address: str,
    secret: str,
) -> tuple[str, str]:
    return (
        secret_digest(normalized_username, secret=secret, purpose="login-subject"),
        secret_digest(source_address, secret=secret, purpose="login-source"),
    )


class IdentityRepository:
    """M1 persistence boundary. It never commits the caller-owned Session."""

    def find_local_user_for_login(self, session: Session, normalized_username: str) -> User | None:
        return session.scalar(
            select(User).where(
                User.username_normalized == normalized_username,
                User.auth_source == "local",
                User.deleted_at.is_(None),
            )
        )

    def role_codes_for_user(self, session: Session, user_id: str) -> frozenset[str]:
        values = session.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        ).all()
        return frozenset(values)

    def resolve_session(self, session: Session, token_digest: str) -> SessionIdentityRecord | None:
        row = session.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_digest == token_digest)
        ).one_or_none()
        if row is None:
            return None
        auth_session, user = row
        return SessionIdentityRecord(
            session_id=auth_session.id,
            user_id=user.id,
            session_auth_version=auth_session.auth_version,
            user_auth_version=user.auth_version,
            user_is_active=user.is_active,
            user_deleted_at=user.deleted_at,
            csrf_digest=auth_session.csrf_digest,
            expires_at=auth_session.expires_at,
            idle_expires_at=auth_session.idle_expires_at,
            revoked_at=auth_session.revoked_at,
            roles=self.role_codes_for_user(session, user.id),
        )

    def create_session(
        self,
        session: Session,
        *,
        user_id: str,
        auth_version: int,
        secrets: NewSessionSecrets,
        now: datetime,
    ) -> AuthSession:
        record = AuthSession(
            id=str(uuid4()),
            token_digest=secrets.token_digest,
            user_id=user_id,
            auth_version=auth_version,
            csrf_digest=secrets.csrf_digest,
            expires_at=secrets.expires_at,
            idle_expires_at=secrets.idle_expires_at,
            last_activity_at=now,
        )
        session.add(record)
        return record

    def refresh_session_activity(
        self,
        session: Session,
        *,
        session_id: str,
        now: datetime,
        idle_timeout_minutes: int,
        refresh_interval_seconds: int = SESSION_ACTIVITY_REFRESH_SECONDS,
    ) -> bool:
        cutoff = now - timedelta(seconds=refresh_interval_seconds)
        requested_idle_expiry = now + timedelta(minutes=idle_timeout_minutes)
        result = session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == session_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                AuthSession.idle_expires_at > now,
                AuthSession.last_activity_at <= cutoff,
            )
            .values(
                last_activity_at=now,
                idle_expires_at=func.least(
                    AuthSession.expires_at,
                    func.greatest(AuthSession.idle_expires_at, requested_idle_expiry),
                ),
            )
            .execution_options(synchronize_session=False)
        )
        return bool(result.rowcount)

    def revoke_session(self, session: Session, *, session_id: str, now: datetime, reason: str) -> bool:
        result = session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session=False)
        )
        return bool(result.rowcount)

    def revoke_user_sessions(self, session: Session, *, user_id: str, now: datetime, reason: str) -> int:
        result = session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)


class LoginThrottleRepository:
    """PostgreSQL-atomic login failure accounting with short transactions."""

    def get_state(
        self,
        session: Session,
        *,
        subject_hmac: str,
        source_hmac: str,
    ) -> LoginThrottleState | None:
        row = session.execute(
            select(LoginThrottle.failure_count, LoginThrottle.locked_until).where(
                LoginThrottle.subject_hmac == subject_hmac,
                LoginThrottle.source_hmac == source_hmac,
            )
        ).one_or_none()
        return None if row is None else LoginThrottleState(failure_count=row[0], locked_until=row[1])

    def record_failure(
        self,
        session: Session,
        *,
        subject_hmac: str,
        source_hmac: str,
        now: datetime,
        max_failures: int,
        window_seconds: int,
        lock_seconds: int,
    ) -> LoginThrottleState:
        if min(max_failures, window_seconds, lock_seconds) < 1:
            raise ValueError("登录限流参数必须是正整数")
        window_cutoff = now - timedelta(seconds=window_seconds)
        locked_until = now + timedelta(seconds=lock_seconds)
        window_expired = LoginThrottle.window_started_at <= window_cutoff
        next_count = case((window_expired, 1), else_=LoginThrottle.failure_count + 1)
        next_locked_until = case(
            (LoginThrottle.locked_until > now, LoginThrottle.locked_until),
            (next_count >= max_failures, locked_until),
            else_=None,
        )
        statement = (
            insert(LoginThrottle)
            .values(
                subject_hmac=subject_hmac,
                source_hmac=source_hmac,
                failure_count=1,
                window_started_at=now,
                locked_until=locked_until if max_failures == 1 else None,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_login_throttles_subject_source",
                set_={
                    "failure_count": next_count,
                    "window_started_at": case((window_expired, now), else_=LoginThrottle.window_started_at),
                    "locked_until": next_locked_until,
                    "updated_at": now,
                },
            )
            .returning(LoginThrottle.failure_count, LoginThrottle.locked_until)
        )
        row = session.execute(statement).one()
        return LoginThrottleState(failure_count=row[0], locked_until=row[1])

    def clear(self, session: Session, *, subject_hmac: str, source_hmac: str) -> None:
        session.execute(
            delete(LoginThrottle).where(
                LoginThrottle.subject_hmac == subject_hmac,
                LoginThrottle.source_hmac == source_hmac,
            )
        )
