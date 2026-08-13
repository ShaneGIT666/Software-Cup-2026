from __future__ import annotations

from fastapi import APIRouter, Request, status

from ...core.config import get_settings
from ...core.contracts import V1Response
from ...db import database_status
from ...core.errors import AppError
from ...domains.identity.runtime import validate_identity_runtime_settings
from .responses import v1_error, v1_success


router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=V1Response, summary="存活检查")
def live(request: Request) -> V1Response:
    """Returns success while the API process can receive requests."""

    settings = get_settings()
    return v1_success(
        request,
        {
            "status": "ok",
            "service": "repair-knowledge-assistant",
            "apiVersion": "v1",
            "environment": settings.environment,
        },
    )


@router.get("/health/ready", response_model=V1Response, summary="就绪检查", responses={503: {"model": V1Response}})
def ready(request: Request):  # type: ignore[no-untyped-def]
    """Reports database readiness without making it mandatory for the legacy demo.

    ``APP_DATABASE_REQUIRED=true`` is the production switch. Once enabled, a
    missing or unavailable PostgreSQL dependency makes this endpoint return
    503 so a service manager can stop routing traffic to the instance.
    """

    settings = get_settings()
    db = database_status(settings)
    identity_required = settings.environment == "production" or settings.database_required
    try:
        validate_identity_runtime_settings(settings)
        identity = {"required": identity_required, "healthy": True, "mode": settings.auth_mode, "reason": ""}
    except AppError:
        identity = {
            "required": identity_required,
            "healthy": False,
            "mode": settings.auth_mode,
            "reason": "身份认证配置未就绪",
        }
    ready = (db.healthy or not db.required) and (identity["healthy"] or not identity_required)
    payload = {
        "status": "ok" if ready else "not_ready",
        "database": db.to_dict(),
        "identity": identity,
    }
    if not ready:
        return v1_error(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEPENDENCY_UNAVAILABLE",
            message="关键数据库依赖未就绪",
            details=payload,
        )
    return v1_success(request, payload)
