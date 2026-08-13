from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


_SENSITIVE_V1_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/users",
    "/api/v1/roles",
    "/api/v1/audit-events",
)


class SensitiveResponseCacheMiddleware(BaseHTTPMiddleware):
    """Prevent browser/proxy caching for all M1 identity and audit outcomes."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(_SENSITIVE_V1_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response

