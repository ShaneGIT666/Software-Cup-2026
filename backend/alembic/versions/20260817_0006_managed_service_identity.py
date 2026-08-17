"""Add managed service identities and the pre-activation lifecycle boundary.

Revision ID: 20260817_0006
Revises: 20260814_0005
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


SERVICE_ROWS = (
    (
        "20000000-0000-0000-0000-000000000001",
        "__service_authentication__",
        "认证子系统服务用户",
        "authentication",
    ),
    (
        "20000000-0000-0000-0000-000000000002",
        "__service_bootstrap__",
        "实例引导服务用户",
        "bootstrap",
    ),
    (
        "20000000-0000-0000-0000-000000000003",
        "__service_worker__",
        "后台任务服务用户",
        "worker",
    ),
)
AUTHENTICATION_SERVICE_USER_ID = SERVICE_ROWS[0][0]
SERVICE_USER_IDS_SQL = ", ".join(f"'{row[0]}'" for row in SERVICE_ROWS)


def _drop_audit_update_delete_trigger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_m1_audit_events_append_only ON audit_events")


def _create_audit_update_delete_trigger() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_m1_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION m1_prevent_audit_event_mutation()
        """
    )


def upgrade() -> None:
    op.drop_constraint("ck_users_auth_source", "users", type_="check")
    op.drop_constraint("ck_users_password_by_auth_source", "users", type_="check")
    op.add_column("users", sa.Column("service_key", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        "ck_users_auth_source",
        "users",
        "auth_source IN ('local', 'oidc', 'service')",
    )
    op.create_check_constraint(
        "ck_users_password_by_auth_source",
        "users",
        "(auth_source = 'local' AND password_hash IS NOT NULL) OR "
        "(auth_source IN ('oidc', 'service') AND password_hash IS NULL)",
    )
    op.create_check_constraint(
        "ck_users_service_key_by_auth_source",
        "users",
        "(auth_source = 'service' AND service_key IS NOT NULL) OR "
        "(auth_source <> 'service' AND service_key IS NULL)",
    )
    op.create_index("ix_users_service_key", "users", ["service_key"], unique=True)

    users = sa.table(
        "users",
        sa.column("id", sa.String()),
        sa.column("username", sa.String()),
        sa.column("username_normalized", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("auth_source", sa.String()),
        sa.column("service_key", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("must_change_password", sa.Boolean()),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": user_id,
                "username": username,
                "username_normalized": username,
                "display_name": display_name,
                "password_hash": None,
                "auth_source": "service",
                "service_key": service_key,
                "is_active": True,
                "must_change_password": False,
            }
            for user_id, username, display_name, service_key in SERVICE_ROWS
        ],
    )

    op.create_table(
        "identity_instance_state",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "lifecycle IN ('uninitialized', 'bootstrapped', 'active')",
            name="ck_identity_instance_state_lifecycle",
        ),
        sa.CheckConstraint("id = 'identity'", name="ck_identity_instance_state_singleton"),
        sa.CheckConstraint("version >= 1", name="ck_identity_instance_state_version"),
        sa.CheckConstraint(
            "(lifecycle = 'active' AND activated_at IS NOT NULL AND activated_by_user_id IS NOT NULL) OR "
            "(lifecycle <> 'active' AND activated_at IS NULL AND activated_by_user_id IS NULL)",
            name="ck_identity_instance_state_activation_fields",
        ),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO identity_instance_state (id, lifecycle)
        SELECT 'identity',
               CASE WHEN EXISTS (
                   SELECT 1 FROM users WHERE auth_source <> 'service'
               ) THEN 'bootstrapped' ELSE 'uninitialized' END
        """
    )

    op.add_column("audit_events", sa.Column("initiator_user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_audit_events_initiator_user_id_users",
        "audit_events",
        "users",
        ["initiator_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_audit_events_initiator_user_id",
        "audit_events",
        ["initiator_user_id"],
        unique=False,
    )
    _drop_audit_update_delete_trigger()
    op.execute(
        "UPDATE audit_events SET actor_user_id = "
        f"'{AUTHENTICATION_SERVICE_USER_ID}' WHERE actor_user_id IS NULL"
    )
    _create_audit_update_delete_trigger()
    op.alter_column(
        "audit_events",
        "actor_user_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_events",
        "actor_user_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    _drop_audit_update_delete_trigger()
    op.execute(
        "UPDATE audit_events SET actor_user_id = NULL "
        f"WHERE actor_user_id IN ({SERVICE_USER_IDS_SQL})"
    )
    op.drop_index("ix_audit_events_initiator_user_id", table_name="audit_events")
    op.drop_constraint(
        "fk_audit_events_initiator_user_id_users",
        "audit_events",
        type_="foreignkey",
    )
    op.drop_column("audit_events", "initiator_user_id")

    op.drop_table("identity_instance_state")
    op.execute(f"DELETE FROM users WHERE id IN ({SERVICE_USER_IDS_SQL})")
    op.drop_index("ix_users_service_key", table_name="users")
    op.drop_constraint("ck_users_service_key_by_auth_source", "users", type_="check")
    op.drop_constraint("ck_users_password_by_auth_source", "users", type_="check")
    op.drop_constraint("ck_users_auth_source", "users", type_="check")
    op.drop_column("users", "service_key")
    op.create_check_constraint(
        "ck_users_auth_source",
        "users",
        "auth_source IN ('local', 'oidc')",
    )
    op.create_check_constraint(
        "ck_users_password_by_auth_source",
        "users",
        "(auth_source = 'local' AND password_hash IS NOT NULL) OR "
        "(auth_source = 'oidc' AND password_hash IS NULL)",
    )
    _create_audit_update_delete_trigger()
