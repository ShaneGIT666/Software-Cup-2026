from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Mapping, Protocol
from urllib.parse import urlparse

from ..db.session import database_status
from .config import AppSettings


@dataclass(frozen=True)
class ReadinessProbe:
    """Health reported by a domain without authority to weaken M0 policy."""

    healthy: bool
    reason: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


class ReadinessContributor(Protocol):
    def check(self, settings: AppSettings) -> ReadinessProbe: ...


@dataclass(frozen=True)
class ReadinessRegistration:
    """M0-owned policy for one optional domain readiness contributor."""

    name: str
    module_suffix: str
    required_in_production: bool = False
    required_when_database_required: bool = False

    def is_required(self, settings: AppSettings) -> bool:
        return (self.required_in_production and settings.environment == "production") or (
            self.required_when_database_required and settings.database_is_required
        )


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    required: bool
    healthy: bool
    reason: str = ""
    details: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = dict(self.details)
        data.update(
            {
                "required": self.required,
                "healthy": self.healthy,
                "reason": self.reason,
            }
        )
        return data


@dataclass(frozen=True)
class ReadinessEvaluation:
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.healthy or not check.required for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ok" if self.ready else "not_ready",
            **{check.name: check.to_dict() for check in self.checks},
        }


# The requirement policy belongs to M0. A contributor can report health but
# cannot set ``required=False`` to make a production dependency disappear.
READINESS_REGISTRATIONS = (
    ReadinessRegistration(
        name="identity",
        module_suffix="domains.identity.readiness",
        required_in_production=True,
        required_when_database_required=True,
    ),
    ReadinessRegistration(name="documents", module_suffix="domains.documents.readiness", required_in_production=True),
    ReadinessRegistration(name="workers", module_suffix="workers.readiness", required_in_production=True),
    ReadinessRegistration(name="indexing", module_suffix="indexing.readiness", required_in_production=True),
    ReadinessRegistration(name="rag", module_suffix="domains.rag.readiness", required_in_production=True),
)


def _is_missing_module(exc: ModuleNotFoundError, module_name: str) -> bool:
    missing_name = exc.name or ""
    return module_name == missing_name or module_name.startswith(f"{missing_name}.")


def _foundation_probe(settings: AppSettings) -> ReadinessProbe:
    if settings.environment != "production":
        return ReadinessProbe(healthy=True)

    violations: list[str] = []
    if len(settings.idempotency_secret.encode("utf-8")) < 32:
        violations.append("idempotency_secret")
    if not settings.trusted_origins or any(urlparse(origin).scheme != "https" for origin in settings.trusted_origins):
        violations.append("trusted_https_origins")
    if settings.legacy_surface_mode != "disabled":
        violations.append("legacy_surface")
    return ReadinessProbe(
        healthy=not violations,
        reason="" if not violations else "生产基础配置未就绪",
        details={"violations": tuple(violations)},
    )


def _database_check(settings: AppSettings) -> ReadinessCheck:
    status = database_status(settings)
    return ReadinessCheck(
        name="database",
        required=settings.database_is_required,
        healthy=status.healthy,
        reason=status.reason,
        details={"configured": status.configured, "dialect": status.dialect},
    )


def _load_contributor(registration: ReadinessRegistration) -> ReadinessContributor | None:
    app_package = __package__.rsplit(".core", maxsplit=1)[0]
    module_name = f"{app_package}.{registration.module_suffix}"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if _is_missing_module(exc, module_name):
            return None
        raise
    contributor = getattr(module, "contributor", None)
    if contributor is None or not callable(getattr(contributor, "check", None)):
        raise TypeError(f"{module_name}.contributor 必须实现 check(settings)")
    return contributor


def evaluate_readiness(settings: AppSettings) -> ReadinessEvaluation:
    foundation_probe = _foundation_probe(settings)
    checks: list[ReadinessCheck] = [
        _database_check(settings),
        ReadinessCheck(
            name="foundation",
            required=True,
            healthy=foundation_probe.healthy,
            reason=foundation_probe.reason,
            details=foundation_probe.details,
        ),
    ]
    for registration in READINESS_REGISTRATIONS:
        contributor = _load_contributor(registration)
        if contributor is None:
            if registration.is_required(settings):
                checks.append(
                    ReadinessCheck(
                        name=registration.name,
                        required=True,
                        healthy=False,
                        reason="依赖模块未安装",
                    )
                )
            continue
        try:
            probe = contributor.check(settings)
        except Exception:
            probe = ReadinessProbe(healthy=False, reason="依赖检查执行失败")
        if not isinstance(probe, ReadinessProbe):
            raise TypeError(f"{registration.module_suffix}.contributor.check() 必须返回 ReadinessProbe")
        checks.append(
            ReadinessCheck(
                name=registration.name,
                required=registration.is_required(settings),
                healthy=probe.healthy,
                reason=probe.reason,
                details=probe.details,
            )
        )
    return ReadinessEvaluation(tuple(checks))
