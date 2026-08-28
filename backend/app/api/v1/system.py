from __future__ import annotations

from fastapi import APIRouter, Request, status

from ...core.config import get_settings
from ...core.contracts import ReadinessErrorResponse
from ...core.readiness import evaluate_readiness
from .responses import v1_error, v1_success
from .system_response_models import LiveResponse, ReadyResponse


router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=LiveResponse, summary="存活检查")
def live(request: Request):  # type: ignore[no-untyped-def]
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
        response_model=LiveResponse,
    )


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    response_model_exclude_unset=True,
    summary="就绪检查",
    responses={503: {"model": ReadinessErrorResponse}},
)
def ready(request: Request):  # type: ignore[no-untyped-def]
    """Aggregate M0-owned foundation and optional domain readiness checks.

    Production invariants cannot be downgraded by optional configuration or by
    a domain contributor. Any unhealthy required check returns a generic 503
    response while retaining only sanitised per-check details.
    """

    settings = get_settings()
    evaluation = evaluate_readiness(settings)
    payload = evaluation.to_dict()
    if not evaluation.ready:
        return v1_error(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEPENDENCY_UNAVAILABLE",
            message="关键依赖未就绪",
            details=payload,
        )
    return v1_success(request, payload, response_model=ReadyResponse)
