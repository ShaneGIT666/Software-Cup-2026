from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from .config import AppSettings
from .error_codes import ErrorCode
from .errors import AppError


def _origin_key(value: str, *, allow_path: bool) -> tuple[str, str, int] | None:
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or (not allow_path and parsed.path not in {"", "/"})
            or (not allow_path and (parsed.params or parsed.query or parsed.fragment))
        ):
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    return parsed.scheme.lower(), parsed.hostname.casefold(), port


def require_trusted_browser_origin(request: Request, settings: AppSettings) -> str:
    """Validate browser write origin independently from response CORS policy."""

    candidate = request.headers.get("Origin")
    allow_path = False
    if not candidate:
        candidate = request.headers.get("Referer")
        allow_path = True
    candidate_key = _origin_key(candidate or "", allow_path=allow_path)
    trusted_keys = {_origin_key(origin, allow_path=False) for origin in settings.trusted_origins}
    if candidate_key is None or candidate_key not in trusted_keys:
        raise AppError(
            403,
            ErrorCode.TRUSTED_ORIGIN_REQUIRED,
            "浏览器写请求必须来自受信任来源。",
        )
    scheme, host, port = candidate_key
    default_port = 443 if scheme == "https" else 80
    return f"{scheme}://{host}" if port == default_port else f"{scheme}://{host}:{port}"

