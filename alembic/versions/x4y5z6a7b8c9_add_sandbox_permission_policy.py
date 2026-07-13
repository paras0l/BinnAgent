"""add sandbox permission policy

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "w3x4y5z6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "sandbox_permission_policies",
        sa.Column("scope", sa.String(length=40), primary_key=True),
        sa.Column("profile", sa.String(length=40), nullable=False, server_default="strict"),
        sa.Column("allowed_domains", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

def downgrade() -> None:
    op.drop_table("sandbox_permission_policies")
