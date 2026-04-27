"""Add website source reference to posts.

Revision ID: 003
Revises: 002
Create Date: 2026-04-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("website_source_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_posts_website_source_id",
        "posts",
        "website_sources",
        ["website_source_id"],
        ["id"],
    )
    op.create_index("ix_posts_website_source_id", "posts", ["website_source_id"])


def downgrade() -> None:
    op.drop_index("ix_posts_website_source_id", table_name="posts")
    op.drop_constraint("fk_posts_website_source_id", "posts", type_="foreignkey")
    op.drop_column("posts", "website_source_id")
