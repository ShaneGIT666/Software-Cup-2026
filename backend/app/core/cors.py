from __future__ import annotations

from typing import Any

from .config import AppSettings


# This is intentionally an explicit list. Credentialed browser CORS must not
# accept wildcards, otherwise future session cookies could be sent to an
# unintended origin.
CORS_ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
CORS_ALLOWED_HEADERS = (
    "Accept",
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "If-Match",
    "X-CSRF-Token",
    "X-Request-ID",
)
CORS_EXPOSE_HEADERS = ("X-Request-ID", "ETag")


def cors_middleware_options(settings: AppSettings) -> dict[str, Any]:
    """Return the single CORS policy shared by every HTTP API version."""

    return {
        "allow_origins": list(settings.trusted_origins),
        "allow_credentials": True,
        "allow_methods": list(CORS_ALLOWED_METHODS),
        "allow_headers": list(CORS_ALLOWED_HEADERS),
        "expose_headers": list(CORS_EXPOSE_HEADERS),
        "max_age": 600,
    }
