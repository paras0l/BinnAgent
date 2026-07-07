"""add feishu group learning source config

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-07-08 10:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, Sequence[str], None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group_learning_sources",
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column(
        "group_learning_sources",
        sa.Column("import_mode", sa.String(length=30), nullable=False, server_default="silent"),
    )
    op.add_column(
        "group_learning_sources",
        sa.Column(
            "allowed_senders",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("group_learning_sources", "platform", server_default="feishu")


def downgrade() -> None:
    op.alter_column("group_learning_sources", "platform", server_default="wechat")
    op.drop_column("group_learning_sources", "allowed_senders")
    op.drop_column("group_learning_sources", "import_mode")
    op.drop_column("group_learning_sources", "sync_interval_seconds")
