from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...core.pagination import decode_cursor, encode_cursor
from ...db.session import new_session
from ...domains.audit.repository import AuditRepository, audit_event_view
from ...domains.identity.contracts import Permission
from ...domains.identity.dependencies import require_permissions
from ...domains.identity.http_responses import IdentityNoStoreRoute
from .identity_response_models import AuditEventListResponse
from .responses import v1_page


router = APIRouter(tags=["audit"], route_class=IdentityNoStoreRoute)


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    dependencies=[Depends(require_permissions(Permission.AUDIT_READ))],
    openapi_extra={"x-required-permissions": [Permission.AUDIT_READ.value]},
)
def list_audit_events(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    actorId: str | None = None,
    action: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
):  # type: ignore[no-untyped-def]
    decoded = decode_cursor(cursor) or {}
    try:
        before_time = datetime.fromisoformat(decoded["occurredAt"]) if decoded.get("occurredAt") else None
    except (TypeError, ValueError):
        raise AppError(400, ErrorCode.INVALID_CURSOR, "分页游标无效或已损坏。") from None
    before_id = decoded.get("id")
    if before_id is not None and not isinstance(before_id, str):
        raise AppError(400, ErrorCode.INVALID_CURSOR, "分页游标无效或已损坏。")
    if from_ is not None and to is not None and from_ > to:
        raise AppError(400, ErrorCode.VALIDATION_ERROR, "from 不能晚于 to。")
    with new_session() as session:
        rows = AuditRepository().list_events(
            session,
            limit=limit + 1,
            before_occurred_at=before_time,
            before_id=before_id,
            actor_id=actorId,
            action=action,
            from_time=from_,
            to_time=to,
        )
    visible = rows[:limit]
    next_cursor = None
    if len(rows) > limit and visible:
        last = visible[-1]
        next_cursor = encode_cursor({"occurredAt": last.occurred_at.isoformat(), "id": last.id})
    response = v1_page(
        request,
        [audit_event_view(event) for event in visible],
        next_cursor=next_cursor,
        response_model=AuditEventListResponse,
    )
    if not isinstance(response, JSONResponse):
        response = JSONResponse(content=jsonable_encoder(response, exclude_unset=True))
    response.headers["Cache-Control"] = "no-store"
    return response
