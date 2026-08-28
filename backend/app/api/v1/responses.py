from __future__ import annotations

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...core.contracts import (
    InternalErrorResponse,
    PageMeta,
    ReadinessErrorResponse,
    ResponseMeta,
    V1ErrorResponse,
    V1PageResponse,
    V1Response,
    ValidationErrorResponse,
)
from ...core.error_codes import ErrorCode
from ...core.request_context import request_id_from_request


def v1_success(
    request: Request,
    data: object | None = None,
    *,
    status_code: int = 200,
    response_model: type[BaseModel] | None = None,
) -> BaseModel | JSONResponse:
    model = response_model or V1Response[object | None]
    payload = model(data=data, meta=ResponseMeta(requestId=request_id_from_request(request)))
    if status_code == 200:
        return payload
    body = jsonable_encoder(payload)
    return JSONResponse(status_code=status_code, content=body)  # type: ignore[return-value]


def v1_page(
    request: Request,
    items: list[object],
    *,
    next_cursor: str | None = None,
    status_code: int = 200,
    response_model: type[BaseModel] | None = None,
) -> BaseModel | JSONResponse:
    """Build the M0-owned cursor-pagination envelope for v1 list endpoints."""

    model = response_model or V1PageResponse[object]
    payload = model(
        data={"items": items},
        meta=PageMeta(requestId=request_id_from_request(request), nextCursor=next_cursor),
    )
    if status_code == 200:
        return payload
    body = jsonable_encoder(payload)
    return JSONResponse(status_code=status_code, content=body)  # type: ignore[return-value]


def v1_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> JSONResponse:
    response_model: type[V1ErrorResponse]
    if status_code == 422 and code == ErrorCode.VALIDATION_ERROR:
        response_model = ValidationErrorResponse
    elif status_code == 503 and code == ErrorCode.DEPENDENCY_UNAVAILABLE and details is not None:
        response_model = ReadinessErrorResponse
    elif status_code == 500 and code == ErrorCode.INTERNAL_ERROR:
        response_model = InternalErrorResponse
    else:
        response_model = V1ErrorResponse

    payload = response_model(
        success=False,
        data=None,
        error={"code": code, "message": message, "details": details},
        meta=ResponseMeta(requestId=request_id_from_request(request)),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload, exclude_unset=True),
    )
