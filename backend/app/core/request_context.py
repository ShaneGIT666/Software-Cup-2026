from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def request_id_from_request(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or current_request_id())


def current_request_id() -> str:
    return _request_id.get()


def _new_request_id(candidate: str | None) -> str:
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds a safe request identifier without imposing auth/domain policy."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = _new_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

