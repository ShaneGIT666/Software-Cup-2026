from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


def _test_database_url() -> str:
    value = os.getenv("M1_TEST_POSTGRES_URL", "").strip()
    if not value:
        pytest.skip("未配置 M1_TEST_POSTGRES_URL；真实 PostgreSQL M1 验收未执行")
    parsed = make_url(value)
    if not parsed.drivername.startswith("postgresql"):
        pytest.fail("M1_TEST_POSTGRES_URL 必须是 PostgreSQL")
    if not (parsed.database or "").endswith("_test"):
        pytest.fail("M1_TEST_POSTGRES_URL 必须指向名称以 _test 结尾的专用测试数据库")
    return value


@pytest.fixture(scope="module")
def migrated_postgres():  # type: ignore[no-untyped-def]
    url = _test_database_url()
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    old_url = os.environ.get("APP_DATABASE_URL")
    os.environ["APP_DATABASE_URL"] = url
    upgraded = False
    engine = None
    try:
        command.upgrade(config, "head")
        upgraded = True
        engine = create_engine(url, future=True)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if upgraded:
            command.downgrade(config, "base")
        if old_url is None:
            os.environ.pop("APP_DATABASE_URL", None)
        else:
            os.environ["APP_DATABASE_URL"] = old_url


def test_m1_online_migration_has_identity_audit_and_independent_throttle_tables(migrated_postgres) -> None:
    inspector = inspect(migrated_postgres)
    tables = set(inspector.get_table_names())

    assert {
        "outbox_events",
        "users",
        "roles",
        "user_roles",
        "auth_sessions",
        "login_throttle_buckets",
        "audit_events",
        "identity_instance_state",
    }.issubset(tables)
    outbox_columns = {column["name"] for column in inspector.get_columns("outbox_events")}
    assert {"version_id", "request_id", "occurred_at"}.issubset(outbox_columns)
    audit_columns = {column["name"]: column for column in inspector.get_columns("audit_events")}
    assert audit_columns["actor_user_id"]["nullable"] is False
    assert audit_columns["initiator_user_id"]["nullable"] is True
    state_checks = " ".join(
        constraint["sqltext"] or ""
        for constraint in inspector.get_check_constraints("identity_instance_state")
    )
    assert "id = 'identity'" in state_checks
    assert "version >= 1" in state_checks
    assert "activated_by_user_id IS NOT NULL" in state_checks
    with migrated_postgres.connect() as connection:
        roles = set(connection.execute(text("SELECT code FROM roles")).scalars())
        services = set(
            connection.execute(
                text("SELECT service_key FROM users WHERE auth_source = 'service'")
            ).scalars()
        )
        lifecycle = connection.execute(
            text("SELECT lifecycle FROM identity_instance_state WHERE id = 'identity'")
        ).scalar_one()
    assert roles == {"technician", "reviewer", "knowledge_manager", "system_admin", "auditor"}
    assert services == {"authentication", "bootstrap", "worker"}
    assert lifecycle == "uninitialized"


def test_m1_audit_trigger_rejects_mutation_online(migrated_postgres) -> None:
    with migrated_postgres.begin() as connection:
        event_id = connection.execute(
            text(
                "INSERT INTO audit_events "
                "(id, actor_user_id, action, target_type, target_id, result, request_id, metadata) "
                "VALUES (:id, :actor, 'integration.test', 'test', 'test', 'success', 'integration', '{}'::jsonb) "
                "RETURNING id"
            ),
            {
                "id": str(uuid4()),
                "actor": "20000000-0000-0000-0000-000000000001",
            },
        ).scalar_one()
    with pytest.raises(DBAPIError):
        with migrated_postgres.begin() as connection:
            connection.execute(
                text("UPDATE audit_events SET result = 'changed' WHERE id = :id"),
                {"id": event_id},
            )


def test_m1_throttle_buckets_are_independent_online(migrated_postgres) -> None:
    with migrated_postgres.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO login_throttle_buckets "
                "(id, bucket_type, bucket_hmac, failure_count, window_started_at) VALUES "
                "(:subject_id, 'subject', :subject, 1, now()), "
                "(:source_id, 'source', :source, 1, now())"
            ),
            {
                "subject_id": str(uuid4()),
                "source_id": str(uuid4()),
                "subject": "s" * 64,
                "source": "i" * 64,
            },
        )
    with migrated_postgres.connect() as connection:
        rows = set(
            connection.execute(
                text("SELECT bucket_type, bucket_hmac FROM login_throttle_buckets")
            ).tuples()
        )
    assert ("subject", "s" * 64) in rows
    assert ("source", "i" * 64) in rows
