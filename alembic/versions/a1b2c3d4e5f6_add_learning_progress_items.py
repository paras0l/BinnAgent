"""add learning progress items

Revision ID: a1b2c3d4e5f6
Revises: 9e4f5a6b7c8d
Create Date: 2026-06-17 20:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9e4f5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_progress_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="opened"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opened_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_learning_progress_items_learner_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "learner_id",
            "skill",
            "item_id",
            name="uq_learning_progress_learner_skill_item",
        ),
    )
    op.create_index(
        "ix_learning_progress_items_learner_skill",
        "learning_progress_items",
        ["learner_id", "skill"],
    )
    op.create_index(
        "ix_learning_progress_items_learner_skill_favorite",
        "learning_progress_items",
        ["learner_id", "skill", "is_favorite"],
    )
    op.create_index(
        "ix_learning_progress_items_learner_skill_learned_at",
        "learning_progress_items",
        ["learner_id", "skill", "learned_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_progress_items_learner_skill_learned_at",
        table_name="learning_progress_items",
    )
    op.drop_index(
        "ix_learning_progress_items_learner_skill_favorite",
        table_name="learning_progress_items",
    )
    op.drop_index("ix_learning_progress_items_learner_skill", table_name="learning_progress_items")
    op.drop_table("learning_progress_items")
