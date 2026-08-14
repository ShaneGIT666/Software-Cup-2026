from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .config import get_settings


def is_legacy_surface_path(path: str) -> bool:
    if path == "/api/v1" or path.startswith("/api/v1/"):
        return False
    return (
        path == "/api"
        or path.startswith("/api/")
        or path == "/uploads"
        or path.startswith("/uploads/")
        or path == "/knowledge"
        or path.startswith("/knowledge/")
    )


def _is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ip_address(request.client.host).is_loopback
    except ValueError:
        return False


class LegacySurfaceMiddleware(BaseHTTPMiddleware):
    """Central compatibility guard; domains never patch individual old routes."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not is_legacy_surface_path(request.url.path):
            return await call_next(request)
        mode = get_settings().legacy_surface_mode
        if mode == "enabled" or (mode == "loopback" and _is_loopback_request(request)):
            return await call_next(request)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
