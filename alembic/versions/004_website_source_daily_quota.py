"""Add daily quota to website sources.

Revision ID: 004
Revises: 003
Create Date: 2026-04-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "website_sources",
        sa.Column("daily_quota", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("website_sources", "daily_quota")
