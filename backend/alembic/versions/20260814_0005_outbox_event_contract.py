"""Complete the versioned transactional outbox event contract.

Revision ID: 20260814_0005
Revises: 20260813_0004
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260814_0005"
down_revision = "20260813_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("version_id", sa.String(length=64), nullable=True))
    op.add_column("outbox_events", sa.Column("request_id", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True))

    # Preserve any prototype rows without pretending they came from a real
    # version/request. New writes always provide the explicit contract fields.
    op.execute("UPDATE outbox_events SET version_id = 'legacy:' || id WHERE version_id IS NULL")
    op.execute("UPDATE outbox_events SET request_id = 'legacy:' || id WHERE request_id IS NULL")
    op.execute("UPDATE outbox_events SET occurred_at = created_at WHERE occurred_at IS NULL")

    op.alter_column("outbox_events", "version_id", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("outbox_events", "request_id", existing_type=sa.String(length=128), nullable=False)
    op.alter_column(
        "outbox_events",
        "occurred_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_index("ix_outbox_events_request_id", "outbox_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_outbox_events_request_id", table_name="outbox_events")
    op.drop_column("outbox_events", "occurred_at")
    op.drop_column("outbox_events", "request_id")
    op.drop_column("outbox_events", "version_id")
