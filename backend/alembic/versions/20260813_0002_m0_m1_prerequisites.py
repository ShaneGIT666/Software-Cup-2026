"""Create shared idempotency records for M0 domain write APIs.

Revision ID: 20260813_0002
Revises: 20260812_0001
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260813_0002"
down_revision = "20260812_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "actor_id", "idempotency_key", name="uq_idempotency_scope_actor_key"),
    )
    op.create_index("ix_idempotency_records_scope", "idempotency_records", ["scope"], unique=False)
    op.create_index("ix_idempotency_records_actor_id", "idempotency_records", ["actor_id"], unique=False)
    op.create_index("ix_idempotency_records_state", "idempotency_records", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_state", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_actor_id", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_scope", table_name="idempotency_records")
    op.drop_table("idempotency_records")
