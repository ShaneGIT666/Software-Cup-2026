from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ...core.contracts import ErrorBody, ResponseMeta, V1Response
from ...core.request_context import request_id_from_request


def v1_success(request: Request, data: Any = None, *, status_code: int = 200) -> V1Response:
    return V1Response(data=data, meta=ResponseMeta(requestId=request_id_from_request(request)))


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
