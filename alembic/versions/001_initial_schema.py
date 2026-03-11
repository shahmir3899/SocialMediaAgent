"""Initial database schema.

Revision ID: 001
Revises: None
Create Date: 2026-02-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Accounts table
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.Enum("FACEBOOK", "INSTAGRAM", name="platform"), nullable=False),
        sa.Column("page_id", sa.String(255), nullable=False),
        sa.Column("page_name", sa.String(255), nullable=False),
        sa.Column("access_token", sa.String(1024), nullable=False),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id"),
    )

    # Posts table
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PENDING", "APPROVED", "SCHEDULED", "POSTED", "FAILED", name="poststatus"),
            nullable=False,
        ),
        sa.Column("mode", sa.Enum("AUTO", "MANUAL", name="postmode"), nullable=False),
        sa.Column(
            "post_type",
            sa.Enum("EDUCATIONAL", "ENGAGEMENT", "PROMOTIONAL", "QUOTE", "ANNOUNCEMENT", name="posttype"),
            nullable=False,
        ),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("image_prompt", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Post logs table
    op.create_table(
        "post_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("platform_response", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("success", sa.Boolean(), default=False, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Approval queue table
    op.create_table(
        "approval_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="approvalstatus"),
            nullable=False,
        ),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id"),
    )

    # Indexes
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_platform", "posts", ["platform"])
    op.create_index("ix_posts_scheduled_time", "posts", ["scheduled_time"])
    op.create_index("ix_post_logs_post_id", "post_logs", ["post_id"])
    op.create_index("ix_approval_queue_status", "approval_queue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_approval_queue_status")
    op.drop_index("ix_post_logs_post_id")
    op.drop_index("ix_posts_scheduled_time")
    op.drop_index("ix_posts_platform")
    op.drop_index("ix_posts_status")
    op.drop_table("approval_queue")
    op.drop_table("post_logs")
    op.drop_table("posts")
    op.drop_table("accounts")
