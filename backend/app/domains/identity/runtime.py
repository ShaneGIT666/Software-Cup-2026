from __future__ import annotations

from ...core.config import AppSettings
from ...core.error_codes import ErrorCode
from ...core.errors import AppError


def validate_identity_runtime_settings(settings: AppSettings) -> None:
    """Fail closed when an M1 authentication entry point is actually enabled.

    The M0 application foundation reads settings while assembling global CORS,
    before M1 routes exist. Keeping identity readiness here prevents unfinished
    M1 work from breaking the legacy compatibility process while still making
    delivered login/dependency entry points reject unsafe configuration.
    """

    if settings.auth_mode != "local":
        raise AppError(
            503,
            ErrorCode.AUTH_MODE_UNAVAILABLE,
            "当前版本尚未启用所配置的身份认证模式。",
        )
    if not settings.auth_secret:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "身份认证运行时的 APP_AUTH_SECRET 未配置。",
        )
    if len(settings.auth_secret.encode("utf-8")) < 32:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "身份认证运行时的 APP_AUTH_SECRET 必须至少为 32 字节。",
        )
