from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import AppSettings, get_settings
from ..core.error_codes import ErrorCode
from ..core.errors import AppError


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


@contextmanager
def new_session() -> Iterator[Session]:
    """Create and own one short transaction using the shared M0 engine.

    Callers may flush but must not commit or roll back.  The context owns the
    full transaction lifecycle and always closes the Session.
    """

    global _session_factory
    try:
        if _session_factory is None:
            get_engine()
    except (RuntimeError, SQLAlchemyError) as exc:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "关键数据库依赖未就绪。",
        ) from exc
    assert _session_factory is not None
    with _session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            if isinstance(exc, (InterfaceError, OperationalError, SQLAlchemyTimeoutError)):
                raise AppError(
                    503,
                    ErrorCode.DEPENDENCY_UNAVAILABLE,
                    "关键数据库依赖未就绪。",
                ) from exc
            raise


def get_session() -> Iterator[Session]:
    """FastAPI request Session with stable dependency-unavailable failures."""

    with new_session() as session:
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
            reason="数据库连接失败",
        )


def dispose_engine() -> None:
    """Release pooled connections. Used by tests and orderly service shutdown."""

    global _engine, _engine_url, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    _session_factory = None
