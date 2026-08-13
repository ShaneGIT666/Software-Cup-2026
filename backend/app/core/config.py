from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def is_postgres_database(self) -> bool:
        scheme = urlparse(self.database_url).scheme
        return scheme in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}


def get_settings() -> AppSettings:
    environment = os.getenv("APP_ENV", "development").strip().lower() or "development"
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
    )
