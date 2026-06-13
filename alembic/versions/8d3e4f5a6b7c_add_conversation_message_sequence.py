"""add conversation message sequence

Revision ID: 8d3e4f5a6b7c
Revises: 7c2d9e1f3a4b
Create Date: 2026-06-13 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8d3e4f5a6b7c"
down_revision: Union[str, Sequence[str], None] = "7c2d9e1f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        WITH ordered_messages AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY thread_id
                    ORDER BY created_at ASC, id ASC
                ) AS sequence
            FROM conversation_messages
        )
        UPDATE conversation_messages
        SET sequence = ordered_messages.sequence
        FROM ordered_messages
        WHERE conversation_messages.id = ordered_messages.id
        """
    )
    op.alter_column("conversation_messages", "sequence", nullable=False)
    op.create_unique_constraint(
        "uq_conversation_messages_thread_sequence",
        "conversation_messages",
        ["thread_id", "sequence"],
    )
    op.create_index(
        "ix_conversation_messages_learner_thread_sequence",
        "conversation_messages",
        ["learner_id", "thread_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_messages_learner_thread_sequence",
        table_name="conversation_messages",
    )
    op.drop_constraint(
        "uq_conversation_messages_thread_sequence",
        "conversation_messages",
        type_="unique",
    )
    op.drop_column("conversation_messages", "sequence")
