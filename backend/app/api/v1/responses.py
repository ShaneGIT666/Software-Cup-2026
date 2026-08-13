from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ...core.contracts import ErrorBody, PageData, PageMeta, V1PageResponse, ResponseMeta, V1Response
from ...core.request_context import request_id_from_request


def v1_success(request: Request, data: Any = None, *, status_code: int = 200) -> V1Response:
    payload = V1Response(data=data, meta=ResponseMeta(requestId=request_id_from_request(request)))
    if status_code == 200:
        return payload
    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return JSONResponse(status_code=status_code, content=body)  # type: ignore[return-value]


def v1_page(
    request: Request,
    items: list[Any],
    *,
    next_cursor: str | None = None,
    status_code: int = 200,
) -> V1PageResponse:
    """Build the M0-owned cursor-pagination envelope for v1 list endpoints."""

    payload = V1PageResponse(
        data=PageData(items=items),
        meta=PageMeta(requestId=request_id_from_request(request), nextCursor=next_cursor),
    )
    if status_code == 200:
        return payload
    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return JSONResponse(status_code=status_code, content=body)  # type: ignore[return-value]


def v1_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    payload = V1Response(
        success=False,
        error=ErrorBody(code=code, message=message, details=details),
        meta=ResponseMeta(requestId=request_id_from_request(request)),
    )
    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return JSONResponse(status_code=status_code, content=body)
