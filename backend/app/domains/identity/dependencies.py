from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ...core.config import AppSettings, get_settings
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...core.trusted_origins import require_trusted_browser_origin
from ...db.session import get_session
from .authorization import permissions_for_roles, require_permission_set
from .contracts import CurrentUser, Permission
from .repository import IdentityRepository, SessionIdentityRecord
from .runtime import validate_identity_runtime_settings
from .sessions import csrf_token_for_session, secret_digest, secrets_equal, session_is_active, utc_now


_REQUEST_SESSION_STATE = "m1_identity_session"
_REQUEST_TOKEN_STATE = "m1_identity_token"


def get_identity_repository() -> IdentityRepository:
    return IdentityRepository()


def _authentication_error(code: str = ErrorCode.AUTHENTICATION_REQUIRED) -> AppError:
    return AppError(401, code, "当前会话无效或已过期，请重新登录。")


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    repository: Annotated[IdentityRepository, Depends(get_identity_repository)],
) -> CurrentUser:
    validate_identity_runtime_settings(settings)
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise _authentication_error()

    record = repository.resolve_session(
        session,
        secret_digest(raw_token, secret=settings.auth_secret),
    )
    now = utc_now()
    if (
        record is None
        or not record.user_is_active
        or record.user_deleted_at is not None
        or record.session_auth_version != record.user_auth_version
        or not session_is_active(
            expires_at=record.expires_at,
            idle_expires_at=record.idle_expires_at,
            revoked_at=record.revoked_at,
            now=now,
        )
    ):
        raise _authentication_error(ErrorCode.SESSION_EXPIRED)

    if repository.refresh_session_activity(
        session,
        session_id=record.session_id,
        now=now,
        idle_timeout_minutes=settings.session_idle_timeout_minutes,
    ):
        # The refresh occurs before endpoint business work and only touches the
        # current M1 session row. Commit it here so a later endpoint failure
        # cannot roll back the independently valid session activity update.
        session.commit()

    current_user = CurrentUser(
        id=record.user_id,
        roles=record.roles,
        permissions=permissions_for_roles(record.roles),
        session_id=record.session_id,
    )
    setattr(request.state, _REQUEST_SESSION_STATE, record)
    setattr(request.state, _REQUEST_TOKEN_STATE, raw_token)
    request.state.current_user = current_user
    return current_user


def require_permissions(*permissions: str | Permission) -> Callable[..., CurrentUser]:
    def dependency(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        require_permission_set(current_user, *permissions)
        return current_user

    return dependency


def require_csrf(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> CurrentUser:
    del current_user  # identity was validated by the dependency above
    record = getattr(request.state, _REQUEST_SESSION_STATE, None)
    raw_token = getattr(request.state, _REQUEST_TOKEN_STATE, "")
    provided = request.headers.get("X-CSRF-Token", "")
    if not isinstance(record, SessionIdentityRecord) or not raw_token or not provided:
        raise AppError(403, ErrorCode.CSRF_INVALID, "CSRF 校验失败。")
    expected_token = csrf_token_for_session(raw_token, secret=settings.auth_secret)
    if not secrets_equal(provided, record.csrf_digest, secret=settings.auth_secret) or not secrets_equal(
        expected_token,
        record.csrf_digest,
        secret=settings.auth_secret,
    ):
        raise AppError(403, ErrorCode.CSRF_INVALID, "CSRF 校验失败。")
    return request.state.current_user


def require_trusted_write_origin(
    request: Request,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> str:
    validate_identity_runtime_settings(settings)
    return require_trusted_browser_origin(request, settings)

