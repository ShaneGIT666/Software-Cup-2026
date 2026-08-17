from __future__ import annotations

from ...core.config import AppSettings
from ...core.errors import AppError
from ...core.readiness import ReadinessDetails, ReadinessProbe
from ...db.session import new_session
from .repository import IdentityRepository
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
        if settings.environment == "production":
            try:
                with new_session() as session:
                    state = IdentityRepository().instance_state(session)
            except AppError:
                return ReadinessProbe(
                    healthy=False,
                    reason="身份实例状态不可用",
                    details=ReadinessDetails(mode=settings.auth_mode),
                )
            if state is None or state.lifecycle != "active":
                return ReadinessProbe(
                    healthy=False,
                    reason="身份实例尚未激活",
                    details=ReadinessDetails(mode=settings.auth_mode),
                )
        return ReadinessProbe(healthy=True, details=ReadinessDetails(mode=settings.auth_mode))


contributor = IdentityReadinessContributor()
