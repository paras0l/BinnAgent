"""add explore feature preferences

Revision ID: 9e4f5a6b7c8d
Revises: 8d3e4f5a6b7c
Create Date: 2026-06-13 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "9e4f5a6b7c8d"
down_revision: Union[str, Sequence[str], None] = "8d3e4f5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "explore_feature_preferences",
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("feature_id", sa.String(length=100), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_explore_feature_preferences_learner_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "feature_id",
            name="uq_explore_feature_preferences_learner_feature",
        ),
    )
    op.create_index(
        "ix_explore_feature_preferences_learner_id",
        "explore_feature_preferences",
        ["learner_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_explore_feature_preferences_learner_id",
        table_name="explore_feature_preferences",
    )
    op.drop_table("explore_feature_preferences")
