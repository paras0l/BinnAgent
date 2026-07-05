"""add parser run progress

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-07-04 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parser_runs",
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="queued"),
    )
    op.add_column(
        "parser_runs",
        sa.Column("progress", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.alter_column("parser_runs", "stage", server_default=None)
    op.alter_column("parser_runs", "progress", server_default=None)


def downgrade() -> None:
    op.drop_column("parser_runs", "progress")
    op.drop_column("parser_runs", "stage")
