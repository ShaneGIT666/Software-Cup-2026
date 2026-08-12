from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import AppSettings, get_settings


@dataclass(frozen=True)
class DatabaseStatus:
    configured: bool
    required: bool
    healthy: bool
    dialect: str | None
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_engine: Engine | None = None
_engine_url: str | None = None
_session_factory: sessionmaker[Session] | None = None


def _safe_database_url(url: str) -> URL:
    return make_url(url)


def _assert_supported_database(settings: AppSettings) -> None:
    if not settings.database_configured:
        raise RuntimeError("APP_DATABASE_URL 未配置")
    if not settings.is_postgres_database:
        raise RuntimeError("APP_DATABASE_URL 必须使用 PostgreSQL 连接串")


def get_engine(settings: AppSettings | None = None) -> Engine:
    """Build one PostgreSQL engine per configured URL.

    No connection is opened during import or application start. This keeps the
    legacy prototype runnable while production readiness remains truthful.
    """

    global _engine, _engine_url, _session_factory
    resolved = settings or get_settings()
    _assert_supported_database(resolved)
    if _engine is not None and _engine_url == resolved.database_url:
        return _engine

    # Parse first so malformed URLs fail without exposing credentials in logs.
    _safe_database_url(resolved.database_url)
    _engine = create_engine(
        resolved.database_url,
        pool_pre_ping=True,
        future=True,
        connect_args={"application_name": resolved.application_name},
    )
    _engine_url = resolved.database_url
    _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    global _session_factory
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    with _session_factory() as session:
        yield session


def database_status(settings: AppSettings | None = None) -> DatabaseStatus:
    resolved = settings or get_settings()
    if not resolved.database_configured:
        return DatabaseStatus(
            configured=False,
            required=resolved.database_required,
            healthy=False,
            dialect=None,
            reason="APP_DATABASE_URL 未配置",
        )
    if not resolved.is_postgres_database:
        return DatabaseStatus(
            configured=True,
            required=resolved.database_required,
            healthy=False,
            dialect=None,
            reason="APP_DATABASE_URL 必须使用 PostgreSQL 连接串",
        )
    try:
        engine = get_engine(resolved)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DatabaseStatus(
            configured=True,
            required=resolved.database_required,
            healthy=True,
            dialect=engine.dialect.name,
        )
    except Exception as exc:  # connection drivers can raise DBAPI-specific errors
        return DatabaseStatus(
            configured=True,
            required=resolved.database_required,
            healthy=False,
            dialect="postgresql",
            reason=str(exc),
        )


def dispose_engine() -> None:
    """Release pooled connections. Used by tests and orderly service shutdown."""

    global _engine, _engine_url, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    _session_factory = None
