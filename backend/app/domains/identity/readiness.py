from __future__ import annotations

from ...core.config import AppSettings
from ...core.errors import AppError
from ...core.readiness import ReadinessDetails, ReadinessProbe
from .runtime import validate_identity_runtime_settings


class IdentityReadinessContributor:
    def check(self, settings: AppSettings) -> ReadinessProbe:
        try:
            validate_identity_runtime_settings(settings)
        except AppError:
            return ReadinessProbe(
                healthy=False,
                reason="身份认证配置未就绪",
                details=ReadinessDetails(mode=settings.auth_mode),
            )
        return ReadinessProbe(healthy=True, details=ReadinessDetails(mode=settings.auth_mode))


contributor = IdentityReadinessContributor()
