from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ...db.base import Base


def _uuid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("auth_source IN ('local', 'oidc', 'service')", name="ck_users_auth_source"),
        CheckConstraint(
            "(auth_source = 'local' AND password_hash IS NOT NULL) OR "
            "(auth_source IN ('oidc', 'service') AND password_hash IS NULL)",
            name="ck_users_password_by_auth_source",
        ),
        CheckConstraint(
            "(auth_source = 'service' AND service_key IS NOT NULL) OR "
            "(auth_source <> 'service' AND service_key IS NULL)",
            name="ck_users_service_key_by_auth_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    service_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class IdentityInstanceState(Base):
    __tablename__ = "identity_instance_state"
    __table_args__ = (
        CheckConstraint("id = 'identity'", name="ck_identity_instance_state_singleton"),
        CheckConstraint(
            "lifecycle IN ('uninitialized', 'bootstrapped', 'active')",
            name="ck_identity_instance_state_lifecycle",
        ),
        CheckConstraint("version >= 1", name="ck_identity_instance_state_version"),
        CheckConstraint(
            "(lifecycle = 'active' AND activated_at IS NOT NULL AND activated_by_user_id IS NOT NULL) OR "
            "(lifecycle <> 'active' AND activated_at IS NULL AND activated_by_user_id IS NULL)",
            name="ck_identity_instance_state_activation_fields",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="identity")
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, default="uninitialized")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    assigned_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    __table_args__ = (
        UniqueConstraint("subject_hmac", "source_hmac", name="uq_login_throttles_subject_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_hmac: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_hmac: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LoginThrottleBucket(Base):
    """Independent account/source throttling required by NFR-SEC-07."""

    __tablename__ = "login_throttle_buckets"
    __table_args__ = (
        CheckConstraint("bucket_type IN ('subject', 'source')", name="ck_login_throttle_buckets_type"),
        UniqueConstraint("bucket_type", "bucket_hmac", name="uq_login_throttle_buckets_type_hmac"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bucket_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    bucket_hmac: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
