"""Create M1 local identity, RBAC, session and append-only audit tables.

Revision ID: 20260813_0003
Revises: 20260813_0002
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260813_0003"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


ROLE_ROWS = (
    ("10000000-0000-0000-0000-000000000001", "technician", "检修人员"),
    ("10000000-0000-0000-0000-000000000002", "reviewer", "审核人员"),
    ("10000000-0000-0000-0000-000000000003", "knowledge_manager", "知识管理员"),
    ("10000000-0000-0000-0000-000000000004", "system_admin", "系统管理员"),
    ("10000000-0000-0000-0000-000000000005", "auditor", "审计查看者"),
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("username_normalized", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("auth_source", sa.String(length=16), server_default="local", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("auth_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("auth_source IN ('local', 'oidc')", name="ck_users_auth_source"),
        sa.CheckConstraint(
            "(auth_source = 'local' AND password_hash IS NOT NULL) OR "
            "(auth_source = 'oidc' AND password_hash IS NULL)",
            name="ck_users_password_by_auth_source",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username_normalized", "users", ["username_normalized"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.String()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(
        roles_table,
        [
            {"id": role_id, "code": code, "display_name": display_name, "is_system": True}
            for role_id, code, display_name in ROLE_ROWS
        ],
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("csrf_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_token_digest", "auth_sessions", ["token_digest"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)
    op.create_index("ix_auth_sessions_idle_expires_at", "auth_sessions", ["idle_expires_at"], unique=False)
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"], unique=False)

    op.create_table(
        "login_throttles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_hmac", sa.String(length=64), nullable=False),
        sa.Column("source_hmac", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_hmac", "source_hmac", name="uq_login_throttles_subject_source"),
    )
    op.create_index("ix_login_throttles_subject_hmac", "login_throttles", ["subject_hmac"], unique=False)
    op.create_index("ix_login_throttles_source_hmac", "login_throttles", ["source_hmac"], unique=False)
    op.create_index("ix_login_throttles_locked_until", "login_throttles", ["locked_until"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("occurred_at", "actor_user_id", "action", "target_type", "target_id", "result", "request_id"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column], unique=False)

    op.execute(
        """
        CREATE FUNCTION m1_prevent_audit_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_m1_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION m1_prevent_audit_event_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_m1_audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION m1_prevent_audit_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_m1_audit_events_no_truncate ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS trg_m1_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS m1_prevent_audit_event_mutation()")
    for column in ("request_id", "result", "target_id", "target_type", "action", "actor_user_id", "occurred_at"):
        op.drop_index(f"ix_audit_events_{column}", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_login_throttles_locked_until", table_name="login_throttles")
    op.drop_index("ix_login_throttles_source_hmac", table_name="login_throttles")
    op.drop_index("ix_login_throttles_subject_hmac", table_name="login_throttles")
    op.drop_table("login_throttles")
    op.drop_index("ix_auth_sessions_revoked_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_idle_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_digest", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_roles")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_username_normalized", table_name="users")
    op.drop_table("users")
