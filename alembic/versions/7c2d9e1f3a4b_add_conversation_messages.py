"""add conversation messages

Revision ID: 7c2d9e1f3a4b
Revises: 4b1f2c3d4e5f
Create Date: 2026-06-13 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7c2d9e1f3a4b"
down_revision: Union[str, Sequence[str], None] = "4b1f2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_messages",
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("skill_focus", sa.String(length=50), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            name="fk_conversation_messages_learner_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["agent_threads.id"],
            name="fk_conversation_messages_thread_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_learner_id",
        "conversation_messages",
        ["learner_id"],
    )
    op.create_index(
        "ix_conversation_messages_thread_id",
        "conversation_messages",
        ["thread_id"],
    )
    op.create_index(
        "ix_conversation_messages_learner_thread_created",
        "conversation_messages",
        ["learner_id", "thread_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_messages_learner_thread_created",
        table_name="conversation_messages",
    )
    op.drop_index("ix_conversation_messages_thread_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_learner_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
