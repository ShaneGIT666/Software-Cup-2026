from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ...core.config import AppSettings, get_settings
from ...core.concurrency import etag_for_version
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...core.pagination import decode_cursor, encode_cursor
from ...core.request_context import request_id_from_request
from ...db.idempotency import request_fingerprint, validate_idempotency_key
from ...db.session import new_session
from ...domains.identity.admin import UserManagementUseCase, get_user_management_use_case, role_views, user_view
from ...domains.identity.contracts import CurrentUser, Permission
from ...domains.identity.dependencies import require_csrf, require_permissions, require_trusted_write_origin
from ...domains.identity.http_contracts import (
    UserCreateRequest,
    UserPasswordResetRequest,
    UserProfileUpdateRequest,
    UserRolesRequest,
    UserStatusRequest,
)
from ...domains.identity.http_responses import IdentityNoStoreRoute, identity_json_response
from ...domains.identity.repository import IdentityRepository
from ...domains.identity.sessions import utc_now
from .identity_response_models import RolesResponse, UserListResponse, UserResponse
from .responses import v1_page


router = APIRouter(tags=["identity"], route_class=IdentityNoStoreRoute)


def _idempotency_hash(
    *,
    current_user: CurrentUser,
    request: Request,
    payload: dict[str, object],
    settings: AppSettings,
) -> str:
    return request_fingerprint(
        actor_id=current_user.id,
        method=request.method,
        path=request.url.path,
        payload=payload,
        secret=settings.idempotency_secret,
    )


def _etag_response(request: Request, data: object, *, version: int | None, status_code: int = 200):  # type: ignore[no-untyped-def]
    response = identity_json_response(request, data, status_code=status_code, response_model=UserResponse)
    if version is not None:
        response.headers["ETag"] = etag_for_version(version)
    return response


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[Depends(require_permissions(Permission.IAM_USERS_READ))],
    openapi_extra={"x-required-permissions": [Permission.IAM_USERS_READ.value]},
)
def list_users(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    status: str | None = None,
):  # type: ignore[no-untyped-def]
    decoded = decode_cursor(cursor) or {}
    try:
        after_created_at = datetime.fromisoformat(decoded["createdAt"]) if decoded.get("createdAt") else None
    except (TypeError, ValueError):
        raise AppError(400, ErrorCode.INVALID_CURSOR, "分页游标无效或已损坏。") from None
    after_id = decoded.get("id")
    if after_id is not None and not isinstance(after_id, str):
        raise AppError(400, ErrorCode.INVALID_CURSOR, "分页游标无效或已损坏。")
    if status not in {None, "active", "inactive"}:
        raise AppError(400, ErrorCode.VALIDATION_ERROR, "status 只能是 active 或 inactive。")
    with new_session() as session:
        rows = IdentityRepository().list_users(
            session,
            limit=limit + 1,
            after_created_at=after_created_at,
            after_id=after_id,
            is_active=None if status is None else status == "active",
        )
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last_user = visible[-1][0]
        next_cursor = encode_cursor({"createdAt": last_user.created_at.isoformat(), "id": last_user.id})
    response = v1_page(
        request,
        [user_view(user, roles) for user, roles in visible],
        next_cursor=next_cursor,
        response_model=UserListResponse,
    )
    if not isinstance(response, JSONResponse):
        response = JSONResponse(content=jsonable_encoder(response, exclude_unset=True))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_trusted_write_origin)],
    openapi_extra={
        "x-required-permissions": [Permission.IAM_USERS_WRITE.value],
        "x-csrf-required": True,
        "x-trusted-origin-required": True,
    },
)
def create_user(
    request: Request,
    payload: UserCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    _: Annotated[CurrentUser, Depends(require_permissions(Permission.IAM_USERS_WRITE))],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[UserManagementUseCase, Depends(get_user_management_use_case)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):  # type: ignore[no-untyped-def]
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    validated_key = validate_idempotency_key(idempotency_key)
    result = use_case.create_user(
        current_user=current_user,
        username=payload.username,
        display_name=payload.displayName,
        initial_password=payload.initialPassword,
        role_codes=payload.roles,
        idempotency_key=validated_key,
        request_hash=_idempotency_hash(current_user=current_user, request=request, payload=data, settings=settings),
        request_id=request_id_from_request(request),
    )
    return _etag_response(request, result.data, version=result.version, status_code=result.status_code)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_write_origin)],
    openapi_extra={
        "x-required-permissions": [Permission.IAM_USERS_WRITE.value],
        "x-csrf-required": True,
        "x-trusted-origin-required": True,
    },
)
def update_user(
    user_id: str,
    request: Request,
    payload: UserProfileUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    _: Annotated[CurrentUser, Depends(require_permissions(Permission.IAM_USERS_WRITE))],
    use_case: Annotated[UserManagementUseCase, Depends(get_user_management_use_case)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
):  # type: ignore[no-untyped-def]
    result = use_case.update_profile(
        current_user=current_user,
        user_id=user_id,
        display_name=payload.displayName,
        if_match=if_match,
        request_id=request_id_from_request(request),
    )
    return _etag_response(request, result.data, version=result.version)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_write_origin)],
    openapi_extra={
        "x-required-permissions": [Permission.IAM_USERS_WRITE.value],
        "x-csrf-required": True,
        "x-trusted-origin-required": True,
    },
)
def set_user_status(
    user_id: str,
    request: Request,
    payload: UserStatusRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    _: Annotated[CurrentUser, Depends(require_permissions(Permission.IAM_USERS_WRITE))],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[UserManagementUseCase, Depends(get_user_management_use_case)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):  # type: ignore[no-untyped-def]
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data["expectedVersion"] = if_match
    validated_key = validate_idempotency_key(idempotency_key)
    result = use_case.set_status(
        current_user=current_user,
        user_id=user_id,
        is_active=payload.isActive,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=validated_key,
        request_hash=_idempotency_hash(current_user=current_user, request=request, payload=data, settings=settings),
        request_id=request_id_from_request(request),
        now=utc_now(),
    )
    return _etag_response(request, result.data, version=result.version)


@router.put(
    "/users/{user_id}/roles",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_write_origin)],
    openapi_extra={
        "x-required-permissions": [Permission.IAM_ROLES_WRITE.value],
        "x-csrf-required": True,
        "x-trusted-origin-required": True,
    },
)
def set_user_roles(
    user_id: str,
    request: Request,
    payload: UserRolesRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    _: Annotated[CurrentUser, Depends(require_permissions(Permission.IAM_ROLES_WRITE))],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[UserManagementUseCase, Depends(get_user_management_use_case)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):  # type: ignore[no-untyped-def]
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data["expectedVersion"] = if_match
    validated_key = validate_idempotency_key(idempotency_key)
    result = use_case.set_roles(
        current_user=current_user,
        user_id=user_id,
        role_codes=payload.roles,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=validated_key,
        request_hash=_idempotency_hash(current_user=current_user, request=request, payload=data, settings=settings),
        request_id=request_id_from_request(request),
        now=utc_now(),
    )
    return _etag_response(request, result.data, version=result.version)


@router.put(
    "/users/{user_id}/password",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_write_origin)],
    openapi_extra={
        "x-required-permissions": [Permission.IAM_USERS_WRITE.value],
        "x-csrf-required": True,
        "x-trusted-origin-required": True,
    },
)
def reset_user_password(
    user_id: str,
    request: Request,
    payload: UserPasswordResetRequest,
    current_user: Annotated[CurrentUser, Depends(require_csrf)],
    _: Annotated[CurrentUser, Depends(require_permissions(Permission.IAM_USERS_WRITE))],
    settings: Annotated[AppSettings, Depends(get_settings)],
    use_case: Annotated[UserManagementUseCase, Depends(get_user_management_use_case)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):  # type: ignore[no-untyped-def]
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data["expectedVersion"] = if_match
    validated_key = validate_idempotency_key(idempotency_key)
    result = use_case.reset_password(
        current_user=current_user,
        user_id=user_id,
        temporary_password=payload.temporaryPassword,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=validated_key,
        request_hash=_idempotency_hash(current_user=current_user, request=request, payload=data, settings=settings),
        request_id=request_id_from_request(request),
        now=utc_now(),
    )
    return _etag_response(request, result.data, version=result.version)


@router.get(
    "/roles",
    response_model=RolesResponse,
    dependencies=[Depends(require_permissions(Permission.IAM_USERS_READ))],
    openapi_extra={"x-required-permissions": [Permission.IAM_USERS_READ.value]},
)
def list_roles(request: Request):  # type: ignore[no-untyped-def]
    return identity_json_response(request, role_views(), response_model=RolesResponse)
