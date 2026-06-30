"""add reading material histories

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-06-30 15:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reading_material_histories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=30), nullable=False, server_default="general"),
        sa.Column("goal", sa.String(length=30), nullable=False, server_default="mixed"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="reading_workshop"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "learner_id",
            "text_hash",
            name="uq_reading_material_histories_learner_text_hash",
        ),
    )
    op.create_index(
        "ix_reading_material_histories_learner_id",
        "reading_material_histories",
        ["learner_id"],
    )
    op.create_index(
        "ix_reading_material_histories_learner_updated",
        "reading_material_histories",
        ["learner_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reading_material_histories_learner_updated",
        table_name="reading_material_histories",
    )
    op.drop_index(
        "ix_reading_material_histories_learner_id",
        table_name="reading_material_histories",
    )
    op.drop_table("reading_material_histories")
