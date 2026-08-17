from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.api.v1.domain_registry import DOMAIN_ROUTER_MODULES
from backend.app.api.v1.responses import v1_page, v1_success
from backend.app.core.client_address import ClientAddressResolver
from backend.app.core.config import AppSettings, get_settings
from backend.app.core.concurrency import etag_for_version, parse_if_match, require_matching_version
from backend.app.core.cors import CORS_ALLOWED_HEADERS, CORS_EXPOSE_HEADERS, cors_middleware_options
from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.core.pagination import decode_cursor, encode_cursor
from backend.app.core.trusted_origins import require_trusted_browser_origin
from backend.app.db.domain_models import load_domain_models
from backend.app.db.idempotency import request_fingerprint, validate_idempotency_key
from backend.app.main import app
from backend.app.core.legacy_surface import is_legacy_surface_path


def _request_with_id(request_id: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/users", "headers": []})
    request.state.request_id = request_id
    return request


def test_development_default_cors_is_local_and_explicit(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_TRUSTED_ORIGINS", raising=False)

    settings = get_settings()
    policy = cors_middleware_options(settings)

    assert settings.trusted_origins == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert policy["allow_credentials"] is True
    assert "*" not in policy["allow_origins"]
    assert "*" not in policy["allow_methods"]
    assert "*" not in policy["allow_headers"]
    assert {"Idempotency-Key", "If-Match", "X-CSRF-Token"}.issubset(CORS_ALLOWED_HEADERS)
    assert CORS_EXPOSE_HEADERS == ("X-Request-ID", "ETag")


def test_cors_response_exposes_etag_to_the_browser() -> None:
    response = TestClient(app).get(
        "/api/v1/health/live",
        headers={"Origin": "http://localhost:5173"},
    )

    exposed = {item.strip() for item in response.headers["Access-Control-Expose-Headers"].split(",")}
    assert {"X-Request-ID", "ETag"}.issubset(exposed)


def test_cors_middleware_accepts_only_the_configured_development_origin() -> None:
    client = TestClient(app)
    headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,idempotency-key,x-csrf-token",
    }

    allowed = client.options("/api/v1/health/live", headers={**headers, "Origin": "http://localhost:5173"})
    rejected = client.options("/api/v1/health/live", headers={**headers, "Origin": "https://untrusted.example.com"})

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_production_cors_fails_closed_when_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_TRUSTED_ORIGINS", raising=False)
    monkeypatch.setenv("APP_AUTH_SECRET", "test-production-auth-secret")
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")

    assert get_settings().trusted_origins == ()


def test_trusted_origins_reject_wildcards_and_paths(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com/*")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-production-auth-secret")
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")

    with pytest.raises(ValueError, match="APP_TRUSTED_ORIGINS"):
        get_settings()


def test_page_response_uses_the_frozen_cursor_envelope() -> None:
    payload = v1_page(
        _request_with_id("page-contract-001"),
        [{"id": "user-001"}],
        next_cursor="opaque-next-cursor",
    )

    assert payload.dict() == {
        "success": True,
        "data": {"items": [{"id": "user-001"}]},
        "error": None,
        "meta": {"requestId": "page-contract-001", "nextCursor": "opaque-next-cursor"},
    }


def test_success_helper_preserves_non_default_success_status() -> None:
    response = v1_success(_request_with_id("created-contract-001"), {"id": "user-001"}, status_code=201)

    assert response.status_code == 201
    assert response.body == (
        b'{"success":true,"data":{"id":"user-001"},"error":null,'
        b'"meta":{"requestId":"created-contract-001"}}'
    )


def test_domain_router_registry_reserves_m1_without_requiring_it_yet() -> None:
    assert DOMAIN_ROUTER_MODULES[:3] == ("auth", "users", "audit")


def test_domain_model_discovery_is_safe_before_m1_is_delivered() -> None:
    load_domain_models()


def test_m1_model_and_route_contracts_are_referenced_by_m0_discovery() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = (root / "backend" / "app" / "api" / "v1" / "domain_registry.py").read_text(encoding="utf-8")
    model_registry = (root / "backend" / "app" / "db" / "domain_models.py").read_text(encoding="utf-8")

    assert '"auth"' in registry
    assert '"users"' in registry
    assert '"audit"' in registry
    assert '"domains.identity.models"' in model_registry
    assert '"domains.audit.models"' in model_registry


def test_idempotency_key_and_request_fingerprint_contract() -> None:
    key = validate_idempotency_key("create-user:550e8400-e29b-41d4-a716-446655440000")
    first = request_fingerprint(
        actor_id="admin-001",
        method="post",
        path="/api/v1/users",
        payload={"username": "alice", "roles": ["technician"]},
        secret="module0-test-secret",
    )
    equivalent = request_fingerprint(
        actor_id="admin-001",
        method="POST",
        path="/api/v1/users",
        payload={"roles": ["technician"], "username": "alice"},
        secret="module0-test-secret",
    )
    changed = request_fingerprint(
        actor_id="admin-001",
        method="POST",
        path="/api/v1/users",
        payload={"username": "alice", "roles": ["reviewer"]},
        secret="module0-test-secret",
    )

    assert key.startswith("create-user:")
    assert first == equivalent
    assert first != changed


def test_idempotency_fingerprint_requires_a_deployment_secret() -> None:
    with pytest.raises(AppError) as exc_info:
        request_fingerprint(
            actor_id="admin-001",
            method="POST",
            path="/api/v1/users",
            payload={"username": "alice", "password": "not-persisted"},
            secret="",
        )

    assert exc_info.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_invalid_idempotency_key_uses_frozen_error_code() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_idempotency_key("short")

    assert exc_info.value.code == ErrorCode.IDEMPOTENCY_KEY_REQUIRED


def test_m1_identity_error_codes_are_registered_by_m0() -> None:
    assert {
        ErrorCode.INVALID_CREDENTIALS,
        ErrorCode.ACCOUNT_LOCKED,
        ErrorCode.ACCOUNT_DISABLED,
        ErrorCode.SESSION_EXPIRED,
        ErrorCode.CSRF_INVALID,
        ErrorCode.SELF_REVIEW_FORBIDDEN,
        ErrorCode.LAST_ADMIN_PROTECTED,
        ErrorCode.PASSWORD_POLICY_VIOLATION,
        ErrorCode.AUTH_MODE_UNAVAILABLE,
    } == {
        "INVALID_CREDENTIALS",
        "ACCOUNT_LOCKED",
        "ACCOUNT_DISABLED",
        "SESSION_EXPIRED",
        "CSRF_INVALID",
        "SELF_REVIEW_FORBIDDEN",
        "LAST_ADMIN_PROTECTED",
        "PASSWORD_POLICY_VIOLATION",
        "AUTH_MODE_UNAVAILABLE",
    }


def test_srs_auditor_requires_an_explicit_business_role() -> None:
    root = Path(__file__).resolve().parents[1]
    srs = (root / "docs" / "requirements" / "software-requirements-spec.md").read_text(encoding="utf-8")

    assert "默认禁止；需叠加检修人员角色" in srs
    assert "基线权限只能读取脱敏后的审计事件和运行报告" in srs


def test_cursor_codec_is_versioned_opaque_and_rejects_damage() -> None:
    cursor = encode_cursor({"id": "user-001", "createdAt": "2026-08-13T00:00:00Z"})

    assert cursor.startswith("v1.")
    assert "user-001" not in cursor
    assert decode_cursor(cursor) == {"createdAt": "2026-08-13T00:00:00Z", "id": "user-001"}
    assert decode_cursor(None) is None

    with pytest.raises(AppError) as exc_info:
        decode_cursor(cursor + "!")
    assert exc_info.value.code == ErrorCode.INVALID_CURSOR


def test_if_match_contract_uses_strong_version_etags() -> None:
    assert etag_for_version(3) == '"v3"'
    assert parse_if_match('"v3"') == 3
    assert require_matching_version('"v3"', 3) == 3

    with pytest.raises(AppError) as missing:
        parse_if_match(None)
    assert missing.value.status_code == 428
    assert missing.value.code == ErrorCode.PRECONDITION_REQUIRED

    with pytest.raises(AppError) as malformed:
        parse_if_match("3")
    assert malformed.value.code == ErrorCode.INVALID_PRECONDITION

    with pytest.raises(AppError) as stale:
        require_matching_version('"v2"', 3)
    assert stale.value.status_code == 412
    assert stale.value.code == ErrorCode.VERSION_CONFLICT


def test_browser_write_origin_is_checked_server_side(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_TRUSTED_ORIGINS", "https://repair.example.com,http://localhost:5173")
    settings = get_settings()

    origin_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"origin", b"https://repair.example.com")],
        }
    )
    referer_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"referer", b"http://localhost:5173/login?next=%2F")],
        }
    )
    assert require_trusted_browser_origin(origin_request, settings) == "https://repair.example.com"
    assert require_trusted_browser_origin(referer_request, settings) == "http://localhost:5173"

    untrusted = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"origin", b"https://evil.example.com")],
        }
    )
    with pytest.raises(AppError) as exc_info:
        require_trusted_browser_origin(untrusted, settings)
    assert exc_info.value.code == ErrorCode.TRUSTED_ORIGIN_REQUIRED


def _client_address_settings(*cidrs: str) -> AppSettings:
    return AppSettings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
        database_required=True,
        application_name="m0-client-address-test",
        trusted_origins=("http://localhost:5173",),
        idempotency_secret="i" * 32,
        auth_mode="local",
        auth_secret="a" * 32,
        session_cookie_name="repair_session",
        session_cookie_secure=False,
        session_ttl_minutes=480,
        session_idle_timeout_minutes=30,
        auth_max_login_failures=5,
        auth_login_window_seconds=900,
        auth_lock_seconds=900,
        trusted_proxy_cidrs=cidrs,
    )


def _address_request(*, client: str, forwarded_for: str | None = None) -> Request:
    headers = [] if forwarded_for is None else [(b"x-forwarded-for", forwarded_for.encode("ascii"))]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": headers,
            "client": (client, 50000),
            "server": ("testserver", 443),
        }
    )


def test_client_address_ignores_forwarding_header_from_untrusted_peer() -> None:
    resolved = ClientAddressResolver().resolve(
        _address_request(client="198.51.100.8", forwarded_for="192.0.2.50"),
        _client_address_settings("10.0.0.0/8"),
    )

    assert resolved == "198.51.100.8"


def test_client_address_walks_only_explicitly_trusted_proxy_hops() -> None:
    resolver = ClientAddressResolver()
    settings = _client_address_settings("10.0.0.0/8")

    assert resolver.resolve(
        _address_request(client="10.0.0.3", forwarded_for="192.0.2.50, 10.0.0.2"),
        settings,
    ) == "192.0.2.50"
    assert resolver.resolve(
        _address_request(client="10.0.0.3", forwarded_for="192.0.2.50, 198.51.100.9"),
        settings,
    ) == "198.51.100.9"


def test_invalid_trusted_proxy_cidr_fails_configuration(monkeypatch) -> None:
    monkeypatch.setenv("APP_TRUSTED_PROXY_CIDRS", "not-a-network")

    with pytest.raises(ValueError, match="APP_TRUSTED_PROXY_CIDRS"):
        get_settings()


def test_legacy_surface_path_classifier_never_blocks_v1() -> None:
    assert is_legacy_surface_path("/api/search") is True
    assert is_legacy_surface_path("/uploads/manual.pdf") is True
    assert is_legacy_surface_path("/knowledge/documents.json") is True
    assert is_legacy_surface_path("/api/v1/health/live") is False
    assert is_legacy_surface_path("/api/v10/search") is True


def test_legacy_surface_can_be_disabled_without_touching_domain_routes(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "disabled")
    client = TestClient(app)

    assert client.get("/api/health").status_code == 404
    assert client.get("/api/knowledge/documents").status_code == 404
    assert client.get("/uploads/.gitkeep").status_code == 404
    assert client.get("/api/v1/health/live").status_code == 200


def test_production_rejects_enabling_the_legacy_surface(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_LEGACY_SURFACE_MODE", "enabled")
    monkeypatch.setenv("APP_SESSION_COOKIE_NAME", "__Host-repair_session")
    monkeypatch.setenv("APP_SESSION_COOKIE_SECURE", "true")

    with pytest.raises(ValueError, match="禁用旧版"):
        get_settings()
