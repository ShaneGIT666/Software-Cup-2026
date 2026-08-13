from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import AuthSession, LoginThrottleBucket, Role, User, UserRole
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
    display_name: str
    must_change_password: bool
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


@dataclass(frozen=True)
class LoginThrottleSnapshot:
    subject: LoginThrottleState | None
    source: LoginThrottleState | None

    def is_locked(self, now: datetime) -> bool:
        return any(state is not None and state.is_locked(now) for state in (self.subject, self.source))


@dataclass(frozen=True)
class LoginCredentialRecord:
    user_id: str
    password_hash: str
    auth_version: int
    is_active: bool
    deleted_at: datetime | None


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

    def credential_for_login(self, session: Session, normalized_username: str) -> LoginCredentialRecord | None:
        user = self.find_local_user_for_login(session, normalized_username)
        if user is None or user.password_hash is None:
            return None
        return LoginCredentialRecord(
            user_id=user.id,
            password_hash=user.password_hash,
            auth_version=user.auth_version,
            is_active=user.is_active,
            deleted_at=user.deleted_at,
        )

    def credential_for_user(self, session: Session, user_id: str) -> LoginCredentialRecord | None:
        user = session.scalar(
            select(User).where(
                User.id == user_id,
                User.auth_source == "local",
                User.deleted_at.is_(None),
            )
        )
        if user is None or user.password_hash is None:
            return None
        return LoginCredentialRecord(
            user_id=user.id,
            password_hash=user.password_hash,
            auth_version=user.auth_version,
            is_active=user.is_active,
            deleted_at=user.deleted_at,
        )

    def revalidate_login_candidate(
        self,
        session: Session,
        *,
        user_id: str,
        password_hash: str,
        auth_version: int,
    ) -> User | None:
        """Lock and recheck the security state immediately before issuance."""

        return session.scalar(
            select(User)
            .where(
                User.id == user_id,
                User.auth_source == "local",
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                User.password_hash == password_hash,
                User.auth_version == auth_version,
            )
            .with_for_update()
        )

    def role_codes_for_user(self, session: Session, user_id: str) -> frozenset[str]:
        values = session.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        ).all()
        return frozenset(values)

    def roles_by_codes(self, session: Session, role_codes: frozenset[str]) -> list[Role]:
        if not role_codes:
            return []
        return list(session.scalars(select(Role).where(Role.code.in_(role_codes)).order_by(Role.code)).all())

    def lock_user(self, session: Session, user_id: str) -> User | None:
        return session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)).with_for_update())

    def active_system_admin_ids(self, session: Session) -> tuple[str, ...]:
        values = session.scalars(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.code == "system_admin",
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(User.id)
            .with_for_update(of=User)
        ).all()
        return tuple(values)

    def replace_user_roles(
        self,
        session: Session,
        *,
        user_id: str,
        roles: list[Role],
        assigned_by_user_id: str,
    ) -> None:
        session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for role in roles:
            session.add(
                UserRole(
                    user_id=user_id,
                    role_id=role.id,
                    assigned_by_user_id=assigned_by_user_id,
                )
            )

    def list_users(
        self,
        session: Session,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: str | None = None,
        is_active: bool | None = None,
    ) -> list[tuple[User, tuple[str, ...]]]:
        roles = (
            select(func.array_agg(Role.code))
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
        )
        statement = select(User, roles.label("role_codes")).where(User.deleted_at.is_(None))
        if is_active is not None:
            statement = statement.where(User.is_active.is_(is_active))
        if after_created_at is not None and after_id is not None:
            statement = statement.where(
                or_(
                    User.created_at > after_created_at,
                    (User.created_at == after_created_at) & (User.id > after_id),
                )
            )
        rows = session.execute(statement.order_by(User.created_at, User.id).limit(limit)).all()
        return [(user, tuple(role_codes or ())) for user, role_codes in rows]

    def resolve_session(self, session: Session, token_digest: str) -> SessionIdentityRecord | None:
        role_codes = (
            select(func.array_agg(Role.code))
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
        )
        row = session.execute(
            select(AuthSession, User, role_codes.label("role_codes"))
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_digest == token_digest)
        ).one_or_none()
        if row is None:
            return None
        auth_session, user, roles = row
        return SessionIdentityRecord(
            session_id=auth_session.id,
            user_id=user.id,
            session_auth_version=auth_session.auth_version,
            user_auth_version=user.auth_version,
            user_is_active=user.is_active,
            user_deleted_at=user.deleted_at,
            display_name=user.display_name,
            must_change_password=user.must_change_password,
            csrf_digest=auth_session.csrf_digest,
            expires_at=auth_session.expires_at,
            idle_expires_at=auth_session.idle_expires_at,
            revoked_at=auth_session.revoked_at,
            roles=frozenset(roles or ()),
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

    def preserve_current_session_after_security_change(
        self,
        session: Session,
        *,
        user_id: str,
        current_session_id: str,
        auth_version: int,
        now: datetime,
        reason: str,
    ) -> bool:
        """Advance the current session version and revoke every other session."""

        current = session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == current_session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                AuthSession.idle_expires_at > now,
            )
            .values(auth_version=auth_version, last_activity_at=now)
            .execution_options(synchronize_session=False)
        )
        if not current.rowcount:
            return False
        session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.id != current_session_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session=False)
        )
        return True


class LoginThrottleRepository:
    """PostgreSQL-atomic login failure accounting with short transactions."""

    @staticmethod
    def _state_for(row: tuple[int, datetime | None] | None) -> LoginThrottleState | None:
        return None if row is None else LoginThrottleState(failure_count=row[0], locked_until=row[1])

    def get_states(
        self,
        session: Session,
        *,
        subject_hmac: str,
        source_hmac: str,
    ) -> LoginThrottleSnapshot:
        rows = session.execute(
            select(
                LoginThrottleBucket.bucket_type,
                LoginThrottleBucket.failure_count,
                LoginThrottleBucket.locked_until,
            ).where(
                (LoginThrottleBucket.bucket_type == "subject")
                & (LoginThrottleBucket.bucket_hmac == subject_hmac)
                | (LoginThrottleBucket.bucket_type == "source")
                & (LoginThrottleBucket.bucket_hmac == source_hmac)
            )
        ).all()
        values = {row[0]: (row[1], row[2]) for row in rows}
        return LoginThrottleSnapshot(
            subject=self._state_for(values.get("subject")),
            source=self._state_for(values.get("source")),
        )

    def _record_bucket_failure(
        self,
        session: Session,
        *,
        bucket_type: str,
        bucket_hmac: str,
        now: datetime,
        max_failures: int,
        window_seconds: int,
        lock_seconds: int,
    ) -> LoginThrottleState:
        bucket = LoginThrottleBucket
        window_cutoff = now - timedelta(seconds=window_seconds)
        locked_until = now + timedelta(seconds=lock_seconds)
        window_expired = bucket.window_started_at <= window_cutoff
        next_count = case((window_expired, 1), else_=bucket.failure_count + 1)
        next_locked_until = case(
            (bucket.locked_until > now, bucket.locked_until),
            (next_count >= max_failures, locked_until),
            else_=None,
        )
        row = session.execute(
            insert(bucket)
            .values(
                bucket_type=bucket_type,
                bucket_hmac=bucket_hmac,
                failure_count=1,
                window_started_at=now,
                locked_until=locked_until if max_failures == 1 else None,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_login_throttle_buckets_type_hmac",
                set_={
                    "failure_count": next_count,
                    "window_started_at": case((window_expired, now), else_=bucket.window_started_at),
                    "locked_until": next_locked_until,
                    "updated_at": now,
                },
            )
            .returning(bucket.failure_count, bucket.locked_until)
        ).one()
        return LoginThrottleState(failure_count=row[0], locked_until=row[1])

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
    ) -> LoginThrottleSnapshot:
        if min(max_failures, window_seconds, lock_seconds) < 1:
            raise ValueError("登录限流参数必须是正整数")
        subject = self._record_bucket_failure(
            session,
            bucket_type="subject",
            bucket_hmac=subject_hmac,
            now=now,
            max_failures=max_failures,
            window_seconds=window_seconds,
            lock_seconds=lock_seconds,
        )
        source = self._record_bucket_failure(
            session,
            bucket_type="source",
            bucket_hmac=source_hmac,
            now=now,
            max_failures=max_failures,
            window_seconds=window_seconds,
            lock_seconds=lock_seconds,
        )
        return LoginThrottleSnapshot(subject=subject, source=source)

    def clear_subject(self, session: Session, *, subject_hmac: str) -> None:
        session.execute(
            delete(LoginThrottleBucket).where(
                (LoginThrottleBucket.bucket_type == "subject")
                & (LoginThrottleBucket.bucket_hmac == subject_hmac)
            )
        )
