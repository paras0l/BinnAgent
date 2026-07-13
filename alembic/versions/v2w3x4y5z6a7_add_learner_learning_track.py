"""add learner learning track

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, Sequence[str], None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learner_profiles",
        sa.Column("learning_track", sa.String(length=20), nullable=False, server_default="school"),
    )
    op.create_check_constraint(
        "ck_learner_profiles_learning_track",
        "learner_profiles",
        "learning_track IN ('school', 'exam', 'general', 'reading')",
    )
    op.alter_column("learner_profiles", "learning_track", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_learner_profiles_learning_track", "learner_profiles", type_="check")
    op.drop_column("learner_profiles", "learning_track")
