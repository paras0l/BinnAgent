"""default learner learning track to reading

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, Sequence[str], None] = "v2w3x4y5z6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "learner_profiles",
        "learning_track",
        existing_type=sa.String(length=20),
        server_default="reading",
    )


def downgrade() -> None:
    op.alter_column(
        "learner_profiles",
        "learning_track",
        existing_type=sa.String(length=20),
        server_default=None,
    )
