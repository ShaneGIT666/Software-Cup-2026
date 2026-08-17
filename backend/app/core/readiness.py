from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import import_module
from typing import Protocol
from urllib.parse import urlparse

from ..db.session import database_status
from .config import AppSettings


_WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"(?i)(?:^|\s)[a-z]:[\\/]|\\\\")
_UNIX_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|\s)/(?:etc|home|opt|proc|root|run|srv|tmp|usr|var)(?:/|\s|$)")
_SENSITIVE_REASON_MARKERS = (
    "http://",
    "https://",
    "file://",
    "postgresql://",
    "postgresql+",
    "traceback",
    "password",
    "secret",
    "token",
    "api_key",
    "api-key",
)
_GENERIC_UNHEALTHY_REASON = "依赖状态不可用"
_ALLOWED_DIALECTS = frozenset({"postgresql", "postgresql+psycopg", "postgresql+psycopg2"})
_ALLOWED_MODES = frozenset({"local", "oidc"})
_ALLOWED_VIOLATIONS = frozenset({"idempotency_secret", "trusted_https_origins", "legacy_surface"})


def _public_reason(reason: str) -> str:
    if not isinstance(reason, str):
        raise TypeError("readiness reason 必须是字符串")
    value = reason.strip()
    if not value:
        return ""
    folded = value.casefold()
    if (
        len(value) > 160
        or any(character in value for character in ("\r", "\n", "\x00"))
        or "=" in value
        or any(marker in folded for marker in _SENSITIVE_REASON_MARKERS)
        or _WINDOWS_ABSOLUTE_PATH_PATTERN.search(value)
        or _UNIX_ABSOLUTE_PATH_PATTERN.search(value)
    ):
        return _GENERIC_UNHEALTHY_REASON
    return value


@dataclass(frozen=True)
class ReadinessDetails:
    """M0-owned allowlist for public readiness details."""

    configured: bool | None = None
    dialect: str | None = None
    mode: str | None = None
    latency_ms: int | None = None
    violations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.configured is not None and not isinstance(self.configured, bool):
            raise TypeError("readiness configured 必须是布尔值")
        if self.configured is None and self.dialect is not None:
            raise ValueError("readiness dialect 只能与 configured 一起返回")
        if self.dialect is not None and self.dialect not in _ALLOWED_DIALECTS:
            raise ValueError("readiness dialect 不在 M0 白名单中")
        if self.mode is not None and self.mode not in _ALLOWED_MODES:
            raise ValueError("readiness mode 不在 M0 白名单中")
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, int) or self.latency_ms < 0
        ):
            raise ValueError("readiness latency_ms 必须是非负整数")
        if not isinstance(self.violations, tuple) or any(item not in _ALLOWED_VIOLATIONS for item in self.violations):
            raise ValueError("readiness violations 不在 M0 白名单中")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {}
        if self.configured is not None:
            data["configured"] = self.configured
            data["dialect"] = self.dialect
        if self.mode is not None:
            data["mode"] = self.mode
        if self.latency_ms is not None:
            data["latencyMs"] = self.latency_ms
        if self.violations:
            data["violations"] = self.violations
        return data


@dataclass(frozen=True)
class ReadinessProbe:
    """Health reported by a domain without authority to weaken M0 policy."""

    healthy: bool
    reason: str = ""
    details: ReadinessDetails = field(default_factory=ReadinessDetails)

    def __post_init__(self) -> None:
        if not isinstance(self.healthy, bool):
            raise TypeError("readiness healthy 必须是布尔值")
        if not isinstance(self.details, ReadinessDetails):
            raise TypeError("readiness details 必须使用 ReadinessDetails")
        object.__setattr__(self, "reason", _public_reason(self.reason))


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
    details: ReadinessDetails = field(default_factory=ReadinessDetails)

    def __post_init__(self) -> None:
        if not isinstance(self.details, ReadinessDetails):
            raise TypeError("readiness details 必须使用 ReadinessDetails")
        object.__setattr__(self, "reason", _public_reason(self.reason))

    def to_dict(self) -> dict[str, object]:
        data = self.details.to_dict()
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
    ReadinessRegistration(name="knowledge", module_suffix="domains.knowledge.readiness", required_in_production=True),
    ReadinessRegistration(name="devices", module_suffix="domains.devices.readiness", required_in_production=True),
    ReadinessRegistration(name="workflows", module_suffix="domains.workflows.readiness", required_in_production=True),
    ReadinessRegistration(name="workers", module_suffix="workers.readiness", required_in_production=True),
    ReadinessRegistration(name="indexing", module_suffix="indexing.readiness", required_in_production=True),
    ReadinessRegistration(name="rag", module_suffix="domains.rag.readiness", required_in_production=True),
)


def _is_missing_module(exc: ModuleNotFoundError, module_name: str) -> bool:
    missing_name = exc.name or ""
    return module_name == missing_name or module_name.startswith(f"{missing_name}.")


def evaluate_foundation_readiness(settings: AppSettings) -> ReadinessProbe:
    """Return the shared production preflight result for foundation settings."""

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
        details=ReadinessDetails(violations=tuple(violations)),
    )


def _database_check(settings: AppSettings) -> ReadinessCheck:
    status = database_status(settings)
    return ReadinessCheck(
        name="database",
        required=settings.database_is_required,
        healthy=status.healthy,
        reason=status.reason,
        details=ReadinessDetails(configured=status.configured, dialect=status.dialect),
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
    foundation_probe = evaluate_foundation_readiness(settings)
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
