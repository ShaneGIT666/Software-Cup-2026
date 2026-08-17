from __future__ import annotations

import os
from dataclasses import dataclass
from ipaddress import ip_network
from urllib.parse import urlparse


VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if parsed < minimum:
        raise ValueError(f"{name} 必须大于等于 {minimum}")
    return parsed


def parse_trusted_origins(value: str, *, environment: str) -> tuple[str, ...]:
    """Parse an explicit comma-separated browser-origin allowlist.

    Browser origins must be a scheme, host and optional port only.  Paths,
    wildcard values and credentials are deliberately rejected: credentialed
    CORS is the public boundary used by the future cookie-session module.
    """

    raw_origins = [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
    if not raw_origins and environment in {"development", "test"}:
        raw_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

    origins: list[str] = []
    for origin in raw_origins:
        parsed = urlparse(origin)
        if (
            "*" in origin
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(f"APP_TRUSTED_ORIGINS 包含无效来源：{origin}")
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


def parse_trusted_proxy_cidrs(value: str) -> tuple[str, ...]:
    """Validate and normalize the explicit proxy allowlist.

    An empty value means that forwarded client-address headers are never
    trusted.  Host bits are normalized away so equivalent CIDRs do not create
    different runtime policies.
    """

    networks: list[str] = []
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        try:
            normalized = str(ip_network(item, strict=False))
        except ValueError as exc:
            raise ValueError(f"APP_TRUSTED_PROXY_CIDRS 包含无效网段：{item}") from exc
        if normalized not in networks:
            networks.append(normalized)
    return tuple(networks)


@dataclass(frozen=True)
class AppSettings:
    """Settings owned by the production foundation.

    The existing prototype settings remain in their adapters until the related
    domain module is migrated.  New production settings use the ``APP_``
    prefix so they do not silently consume unrelated machine environment
    variables such as ``DATABASE_URL``.
    """

    environment: str
    database_url: str
    database_required: bool
    application_name: str
    trusted_origins: tuple[str, ...]
    idempotency_secret: str
    auth_mode: str
    auth_secret: str
    session_cookie_name: str
    session_cookie_secure: bool
    session_ttl_minutes: int
    session_idle_timeout_minutes: int
    auth_max_login_failures: int
    auth_login_window_seconds: int
    auth_lock_seconds: int
    trusted_proxy_cidrs: tuple[str, ...] = ()
    legacy_surface_mode: str = "enabled"

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def is_postgres_database(self) -> bool:
        scheme = urlparse(self.database_url).scheme
        return scheme in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}

    @property
    def database_is_required(self) -> bool:
        """Production cannot downgrade PostgreSQL to an optional dependency."""

        return self.environment == "production" or self.database_required


def get_settings() -> AppSettings:
    raw_environment = os.getenv("APP_ENV")
    environment = "development" if raw_environment is None else raw_environment.strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError("APP_ENV 只能是 development、test 或 production")
    auth_mode = os.getenv("APP_AUTH_MODE", "local").strip().lower() or "local"
    if auth_mode not in {"local", "oidc"}:
        raise ValueError("APP_AUTH_MODE 只能是 local 或 oidc")

    session_cookie_secure = env_flag("APP_SESSION_COOKIE_SECURE", default=environment == "production")
    session_cookie_name = os.getenv(
        "APP_SESSION_COOKIE_NAME",
        "__Host-repair_session" if environment == "production" else "repair_session",
    ).strip()
    auth_secret = os.getenv("APP_AUTH_SECRET", "").strip()
    legacy_surface_mode = os.getenv(
        "APP_LEGACY_SURFACE_MODE",
        "disabled" if environment == "production" else "enabled",
    ).strip().lower()
    if legacy_surface_mode not in {"enabled", "loopback", "disabled"}:
        raise ValueError("APP_LEGACY_SURFACE_MODE 只能是 enabled、loopback 或 disabled")
    if environment == "production" and legacy_surface_mode != "disabled":
        raise ValueError("生产环境必须禁用旧版 API 与静态文件表面")
    if not session_cookie_name:
        raise ValueError("APP_SESSION_COOKIE_NAME 不能为空")
    if session_cookie_name.startswith("__Host-") and not session_cookie_secure:
        raise ValueError("__Host- Cookie 必须启用 APP_SESSION_COOKIE_SECURE")
    if environment == "production":
        if not session_cookie_secure:
            raise ValueError("生产环境必须启用安全会话 Cookie")
        if not session_cookie_name.startswith("__Host-"):
            raise ValueError("生产环境会话 Cookie 必须使用 __Host- 前缀")

    return AppSettings(
        environment=environment,
        database_url=os.getenv("APP_DATABASE_URL", "").strip(),
        database_required=env_flag("APP_DATABASE_REQUIRED", default=False),
        application_name=os.getenv("APP_DATABASE_APPLICATION_NAME", "repair-knowledge-assistant").strip()
        or "repair-knowledge-assistant",
        trusted_origins=parse_trusted_origins(
            os.getenv("APP_TRUSTED_ORIGINS", ""),
            environment=environment,
        ),
        idempotency_secret=os.getenv("APP_IDEMPOTENCY_SECRET", "").strip(),
        auth_mode=auth_mode,
        auth_secret=auth_secret,
        session_cookie_name=session_cookie_name,
        session_cookie_secure=session_cookie_secure,
        session_ttl_minutes=env_int("APP_SESSION_TTL_MINUTES", 480),
        session_idle_timeout_minutes=env_int("APP_SESSION_IDLE_TIMEOUT_MINUTES", 30),
        auth_max_login_failures=env_int("APP_AUTH_MAX_LOGIN_FAILURES", 5),
        auth_login_window_seconds=env_int("APP_AUTH_LOGIN_WINDOW_SECONDS", 900),
        auth_lock_seconds=env_int("APP_AUTH_LOCK_SECONDS", 900),
        trusted_proxy_cidrs=parse_trusted_proxy_cidrs(os.getenv("APP_TRUSTED_PROXY_CIDRS", "")),
        legacy_surface_mode=legacy_surface_mode,
    )
