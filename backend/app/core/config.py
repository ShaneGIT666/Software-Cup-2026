from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def is_postgres_database(self) -> bool:
        scheme = urlparse(self.database_url).scheme
        return scheme in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}


def get_settings() -> AppSettings:
    return AppSettings(
        environment=os.getenv("APP_ENV", "development").strip().lower() or "development",
        database_url=os.getenv("APP_DATABASE_URL", "").strip(),
        database_required=env_flag("APP_DATABASE_REQUIRED", default=False),
        application_name=os.getenv("APP_DATABASE_APPLICATION_NAME", "repair-knowledge-assistant").strip()
        or "repair-knowledge-assistant",
    )

