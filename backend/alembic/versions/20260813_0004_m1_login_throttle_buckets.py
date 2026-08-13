"""Add independent subject and source login throttle buckets.

Revision ID: 20260813_0004
Revises: 20260813_0003
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260813_0004"
down_revision = "20260813_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_throttle_buckets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bucket_type", sa.String(length=16), nullable=False),
        sa.Column("bucket_hmac", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("bucket_type IN ('subject', 'source')", name="ck_login_throttle_buckets_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_type", "bucket_hmac", name="uq_login_throttle_buckets_type_hmac"),
    )
    op.create_index("ix_login_throttle_buckets_bucket_type", "login_throttle_buckets", ["bucket_type"])
    op.create_index("ix_login_throttle_buckets_bucket_hmac", "login_throttle_buckets", ["bucket_hmac"])
    op.create_index("ix_login_throttle_buckets_locked_until", "login_throttle_buckets", ["locked_until"])


def downgrade() -> None:
    op.drop_index("ix_login_throttle_buckets_locked_until", table_name="login_throttle_buckets")
    op.drop_index("ix_login_throttle_buckets_bucket_hmac", table_name="login_throttle_buckets")
    op.drop_index("ix_login_throttle_buckets_bucket_type", table_name="login_throttle_buckets")
    op.drop_table("login_throttle_buckets")
