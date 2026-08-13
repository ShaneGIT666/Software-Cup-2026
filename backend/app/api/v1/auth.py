from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from ...core.client_address import ClientAddressResolver, get_client_address_resolver
from ...core.config import AppSettings, get_settings
from ...core.contracts import V1Response
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...core.request_context import request_id_from_request
from ...db.idempotency import request_fingerprint, validate_idempotency_key
from ...domains.identity.commands import (
    LogoutUseCase,
    PasswordChangeUseCase,
    get_logout_use_case,
    get_password_change_use_case,
)
from ...domains.identity.contracts import CurrentUser, ResolvedIdentity
from ...domains.identity.dependencies import (
    get_resolved_identity,
    require_csrf,
    require_trusted_write_origin,
)
from ...domains.identity.http_contracts import LoginRequest, PasswordChangeRequest
from ...domains.identity.http_responses import (
    IdentityNoStoreRoute,
    clear_session_cookie,
    identity_json_response,
    set_session_cookie,
)
from ...domains.identity.login import LoginUseCase, get_login_use_case
from ...domains.identity.sessions import csrf_token_for_session, utc_now
from ...domains.identity.transactions import SessionIdentityResolver, get_session_identity_resolver


router = APIRouter(prefix="/auth", tags=["identity"], route_class=IdentityNoStoreRoute)


def _identity_data(resolved: ResolvedIdentity) -> dict[str, object]:
    current = resolved.current_user
    return {
        "user": {
            "id": current.id,
            "displayName": resolved.display_name,
            "roles": sorted(current.roles),
            "permissions": sorted(current.permissions),
            "mustChangePassword": resolved.must_change_password,
        },
        "session": {
            "expiresAt": resolved.expires_at.isoformat(),
            "idleExpiresAt": resolved.idle_expires_at.isoformat(),
        },
    }


@router.post("/login", response_model=V1Response, dependencies=[Depends(require_trusted_write_origin)])
def login(
    request: Request,
    payload: LoginRequest,
    settings: Annotated[AppSettings, Depends(get_settings)],
    client_addresses: Annotated[ClientAddressResolver, Depends(get_client_address_resolver)],
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
    identity_resolver: Annotated[SessionIdentityResolver, Depends(get_session_identity_resolver)],
):  # type: ignore[no-untyped-def]
    result = use_case.authenticate(
        username=payload.username,
        password=payload.password,
        source_address=client_addresses.resolve(request, settings),
        settings=settings,
        request_id=request_id_from_request(request),
        now=utc_now(),
    )
    if not result.authenticated or result.created_session is None:
        raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误。")

    created = result.created_session
    resolved = identity_resolver.resolve(created.secrets.token_digest)
    if resolved is None:
        raise AppError(503, ErrorCode.DEPENDENCY_UNAVAILABLE, "新会话暂时无法读取。")
    current = CurrentUser(
        id=resolved.user_id,
        roles=resolved.roles,
        permissions=frozenset(),
        session_id=resolved.session_id,
    )
    from ...domains.identity.authorization import permissions_for_roles

    identity = ResolvedIdentity(
        current_user=CurrentUser(
            id=current.id,
            roles=current.roles,
            permissions=permissions_for_roles(current.roles),
            session_id=current.session_id,
        ),
        display_name=resolved.display_name,
        must_change_password=resolved.must_change_password,
        expires_at=resolved.expires_at,
        idle_expires_at=resolved.idle_expires_at,
        csrf_digest=resolved.csrf_digest,
    )
    data = _identity_data(identity)
    data["csrfToken"] = created.secrets.csrf_token
    response = identity_json_response(request, data)
    set_session_cookie(response, settings=settings, token=created.secrets.token)
    return response


@router.post("/logout", response_model=V1Response, dependencies=[Depends(require_trusted_write_origin)])
def logout(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[LogoutUseCase, Depends(get_logout_use_case)],
):  # type: ignore[no-untyped-def]
    use_case.execute(current_user=current_user, request_id=request_id_from_request(request), now=utc_now())
    response = identity_json_response(request, {"loggedOut": True})
    clear_session_cookie(response, settings=settings)
    return response


@router.get("/me", response_model=V1Response)
def me(
    request: Request,
    resolved: Annotated[ResolvedIdentity, Depends(get_resolved_identity)],
):  # type: ignore[no-untyped-def]
    return identity_json_response(request, _identity_data(resolved))


@router.get("/csrf", response_model=V1Response)
def csrf(
    request: Request,
    resolved: Annotated[ResolvedIdentity, Depends(get_resolved_identity)],
    settings: Annotated[AppSettings, Depends(get_settings)],
):  # type: ignore[no-untyped-def]
    del resolved
    raw_token = getattr(request.state, "m1_identity_token", "")
    if not raw_token:
        raise AppError(401, ErrorCode.AUTHENTICATION_REQUIRED, "当前会话无效或已过期，请重新登录。")
    return identity_json_response(request, {"csrfToken": csrf_token_for_session(raw_token, secret=settings.auth_secret)})


@router.put("/password", response_model=V1Response, dependencies=[Depends(require_trusted_write_origin)])
def change_password(
    request: Request,
    payload: PasswordChangeRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[PasswordChangeUseCase, Depends(get_password_change_use_case)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):  # type: ignore[no-untyped-def]
    validated_key = validate_idempotency_key(idempotency_key)
    fingerprint = request_fingerprint(
        actor_id=current_user.id,
        method="PUT",
        path="/api/v1/auth/password",
        payload={"currentPassword": payload.currentPassword, "newPassword": payload.newPassword},
        secret=settings.idempotency_secret,
    )
    result = use_case.execute(
        current_user=current_user,
        current_password=payload.currentPassword,
        new_password=payload.newPassword,
        idempotency_key=validated_key,
        request_hash=fingerprint,
        request_id=request_id_from_request(request),
        settings=settings,
        now=utc_now(),
    )
    return identity_json_response(request, dict(result.data), status_code=result.status_code)
