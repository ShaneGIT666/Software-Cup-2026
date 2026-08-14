from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request, Security
from fastapi.security import APIKeyCookie
from ...core.config import AppSettings, get_settings
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...core.trusted_origins import require_trusted_browser_origin
from .authorization import permissions_for_roles, require_permission_set
from .contracts import CurrentUser, Permission, ResolvedIdentity
from .repository import IdentityRepository, SessionIdentityRecord
from .runtime import validate_identity_runtime_settings
from .sessions import csrf_token_for_session, secret_digest, secrets_equal, session_is_active, utc_now
from .transactions import (
    SessionActivityRefresher,
    SessionIdentityResolver,
    get_session_activity_refresher,
    get_session_identity_resolver,
)


_REQUEST_SESSION_STATE = "m1_identity_session"
_REQUEST_TOKEN_STATE = "m1_identity_token"
SESSION_COOKIE_SECURITY = APIKeyCookie(
    name=get_settings().session_cookie_name,
    scheme_name="SessionCookie",
    description=(
        "HttpOnly 会话 Cookie。开发默认名为 repair_session；生产名称由 "
        "APP_SESSION_COOKIE_NAME 配置为 __Host- 前缀，浏览器自动携带。"
    ),
    auto_error=False,
)


def get_identity_repository() -> IdentityRepository:
    return IdentityRepository()


def _authentication_error(code: str = ErrorCode.AUTHENTICATION_REQUIRED) -> AppError:
    return AppError(401, code, "当前会话无效或已过期，请重新登录。")


def get_resolved_identity(
    request: Request,
    settings: Annotated[AppSettings, Depends(get_settings)],
    identity_resolver: Annotated[SessionIdentityResolver, Depends(get_session_identity_resolver)],
    activity_refresher: Annotated[SessionActivityRefresher, Depends(get_session_activity_refresher)],
    _documented_session_cookie: Annotated[str | None, Security(SESSION_COOKIE_SECURITY)] = None,
) -> ResolvedIdentity:
    validate_identity_runtime_settings(settings)
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise _authentication_error()

    record = identity_resolver.resolve(secret_digest(raw_token, secret=settings.auth_secret))
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

    activity_refresher.refresh(
        session_id=record.session_id,
        now=now,
        idle_timeout_minutes=settings.session_idle_timeout_minutes,
    )

    current_user = CurrentUser(
        id=record.user_id,
        roles=record.roles,
        permissions=permissions_for_roles(record.roles),
        session_id=record.session_id,
    )
    setattr(request.state, _REQUEST_SESSION_STATE, record)
    setattr(request.state, _REQUEST_TOKEN_STATE, raw_token)
    request.state.current_user = current_user
    resolved = ResolvedIdentity(
        current_user=current_user,
        display_name=record.display_name,
        must_change_password=record.must_change_password,
        expires_at=record.expires_at,
        idle_expires_at=record.idle_expires_at,
        csrf_digest=record.csrf_digest,
    )
    request.state.resolved_identity = resolved
    return resolved


def get_current_user(
    resolved: Annotated[ResolvedIdentity, Depends(get_resolved_identity)],
) -> CurrentUser:
    return resolved.current_user


def require_permissions(*permissions: str | Permission) -> Callable[..., CurrentUser]:
    def dependency(
        request: Request,
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        resolved = getattr(request.state, "resolved_identity", None)
        if isinstance(resolved, ResolvedIdentity) and resolved.must_change_password:
            raise AppError(403, ErrorCode.FORBIDDEN, "当前账户必须先修改临时密码。")
        require_permission_set(current_user, *permissions)
        return current_user

    return dependency


def require_csrf(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    csrf_header: Annotated[
        str | None,
        Header(
            alias="X-CSRF-Token",
            description="由 /api/v1/auth/login 或 /api/v1/auth/csrf 返回，并与当前会话绑定。",
        ),
    ] = None,
) -> CurrentUser:
    del current_user  # identity was validated by the dependency above
    record = getattr(request.state, _REQUEST_SESSION_STATE, None)
    raw_token = getattr(request.state, _REQUEST_TOKEN_STATE, "")
    provided = csrf_header or request.headers.get("X-CSRF-Token", "")
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
