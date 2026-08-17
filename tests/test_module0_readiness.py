from __future__ import annotations

import pytest

from backend.app.core.config import get_settings
from backend.app.core.readiness import (
    READINESS_REGISTRATIONS,
    ReadinessDetails,
    ReadinessProbe,
    ReadinessRegistration,
    evaluate_readiness,
)


def test_readiness_required_policy_is_owned_by_m0(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.setenv("APP_AUTH_SECRET", "a" * 32)
    monkeypatch.setenv("APP_IDEMPOTENCY_SECRET", "i" * 32)
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com")
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "disabled")

    registration = ReadinessRegistration(
        name="domain",
        module_suffix="domains.example.readiness",
        required_in_production=True,
    )

    assert registration.is_required(get_settings()) is True
    assert not hasattr(ReadinessProbe(healthy=True), "required")


def test_readiness_aggregator_discovers_identity_without_importing_it_from_system(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.setenv("APP_AUTH_SECRET", "a" * 32)

    evaluation = evaluate_readiness(get_settings())

    checks = {check.name: check for check in evaluation.checks}
    assert checks["identity"].healthy is True
    assert checks["identity"].required is False
    assert checks["identity"].details.mode == "local"


def test_readiness_registry_reserves_every_target_product_contributor() -> None:
    assert {registration.name for registration in READINESS_REGISTRATIONS} == {
        "identity",
        "documents",
        "knowledge",
        "devices",
        "workflows",
        "workers",
        "indexing",
        "rag",
    }


def test_readiness_public_details_are_typed_and_allowlisted() -> None:
    with pytest.raises(TypeError, match="ReadinessDetails"):
        ReadinessProbe(healthy=False, details={"databaseUrl": "postgresql://secret"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="M0 白名单"):
        ReadinessDetails(mode="secret-looking-but-valid-label")

    details = ReadinessDetails(
        configured=True,
        dialect="postgresql+psycopg",
        mode="local",
        latency_ms=12,
        violations=("trusted_https_origins",),
    )

    assert details.to_dict() == {
        "configured": True,
        "dialect": "postgresql+psycopg",
        "mode": "local",
        "latencyMs": 12,
        "violations": ("trusted_https_origins",),
    }


def test_readiness_reason_replaces_sensitive_paths_and_connection_strings() -> None:
    probe = ReadinessProbe(
        healthy=False,
        reason="postgresql://admin:secret@db.internal/repair",
    )

    assert probe.reason == "依赖状态不可用"
    assert "secret" not in probe.reason


def test_existing_contributor_import_failures_are_not_hidden(monkeypatch) -> None:
    import backend.app.core.readiness as readiness_module

    real_import = readiness_module.import_module

    def broken_import(name: str):
        if name.endswith("domains.identity.readiness"):
            raise ModuleNotFoundError("missing nested dependency", name="identity_nested_dependency")
        return real_import(name)

    monkeypatch.setattr(readiness_module, "import_module", broken_import)

    try:
        evaluate_readiness(get_settings())
    except ModuleNotFoundError as exc:
        assert exc.name == "identity_nested_dependency"
    else:  # pragma: no cover - protects the discovery contract
        raise AssertionError("existing contributor import failure was hidden")


def test_missing_required_production_contributor_is_unhealthy(monkeypatch) -> None:
    import backend.app.core.readiness as readiness_module

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DATABASE_REQUIRED", "false")
    monkeypatch.setenv("APP_AUTH_SECRET", "a" * 32)
    monkeypatch.setenv("APP_IDEMPOTENCY_SECRET", "i" * 32)
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com")
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "disabled")
    monkeypatch.setattr(readiness_module, "database_status", lambda settings: type("Status", (), {
        "healthy": True,
        "reason": "",
        "configured": True,
        "dialect": "postgresql",
    })())

    evaluation = evaluate_readiness(get_settings())

    checks = {check.name: check for check in evaluation.checks}
    assert checks["documents"].required is True
    assert checks["documents"].healthy is False
    assert checks["documents"].reason == "依赖模块未安装"
    assert checks["knowledge"].healthy is False
    assert checks["devices"].healthy is False
    assert checks["workflows"].healthy is False
    assert evaluation.ready is False
