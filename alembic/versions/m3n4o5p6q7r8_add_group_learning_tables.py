"""add group learning tables

Revision ID: m3n4o5p6q7r8
Revises: l2g3h4i5j6k7
Create Date: 2026-07-07 21:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, Sequence[str], None] = "l2g3h4i5j6k7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_learning_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False, server_default="wechat"),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="group"),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("external_group_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_cursor", sa.String(length=500), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_import_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("raw_retention_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column(
            "auto_generate_recommendations",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "auto_write_candidates",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "auto_apply_high_confidence_tagged_signals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_group_learning_sources_learner_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "learner_id",
            "platform",
            "external_group_key",
            name="uq_group_learning_source_learner_external_key",
        ),
    )
    op.create_index(
        "ix_group_learning_sources_learner_id",
        "group_learning_sources",
        ["learner_id"],
    )
    op.create_index(
        "ix_group_learning_sources_learner_status",
        "group_learning_sources",
        ["learner_id", "status"],
    )

    op.create_table(
        "group_learning_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_member_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("analysis_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["group_learning_sources.id"],
            name="fk_group_learning_participants_source_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_group_learning_participants_learner_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "source_id",
            "external_member_key",
            name="uq_group_learning_participant_source_member",
        ),
    )
    op.create_index(
        "ix_group_learning_participants_source_id",
        "group_learning_participants",
        ["source_id"],
    )
    op.create_index(
        "ix_group_learning_participants_source_role",
        "group_learning_participants",
        ["source_id", "role"],
    )
    op.create_index(
        "ix_group_learning_participants_learner",
        "group_learning_participants",
        ["learner_id"],
    )

    op.create_table(
        "group_learning_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("external_member_key", sa.String(length=255), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_type", sa.String(length=30), nullable=False, server_default="text"),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("language_mix", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingestion_status",
            sa.String(length=40),
            nullable=False,
            server_default="processed",
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["group_learning_sources.id"],
            name="fk_group_learning_messages_source_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_group_learning_messages_learner_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "source_id",
            "external_message_id",
            name="uq_group_learning_message_source_external",
        ),
        sa.UniqueConstraint(
            "source_id",
            "content_hash",
            name="uq_group_learning_message_source_hash",
        ),
    )
    op.create_index(
        "ix_group_learning_messages_source_id",
        "group_learning_messages",
        ["source_id"],
    )
    op.create_index(
        "ix_group_learning_messages_learner_id",
        "group_learning_messages",
        ["learner_id"],
    )
    op.create_index(
        "ix_group_learning_messages_source_occurred",
        "group_learning_messages",
        ["source_id", "occurred_at"],
    )
    op.create_index(
        "ix_group_learning_messages_learner_status",
        "group_learning_messages",
        ["learner_id", "ingestion_status"],
    )

    op.create_table(
        "group_learning_signals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_label", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("normalized_note", sa.Text(), nullable=True),
        sa.Column("recommendation_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="candidate"),
        sa.Column("applied_target_type", sa.String(length=50), nullable=True),
        sa.Column("applied_target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["group_learning_messages.id"],
            name="fk_group_learning_signals_message_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_group_learning_signals_learner_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "message_id",
            "signal_type",
            "target_label",
            name="uq_group_learning_signal_message_type_target",
        ),
    )
    op.create_index(
        "ix_group_learning_signals_message_id",
        "group_learning_signals",
        ["message_id"],
    )
    op.create_index(
        "ix_group_learning_signals_learner_id",
        "group_learning_signals",
        ["learner_id"],
    )
    op.create_index(
        "ix_group_learning_signals_learner_status",
        "group_learning_signals",
        ["learner_id", "status"],
    )
    op.create_index(
        "ix_group_learning_signals_learner_type",
        "group_learning_signals",
        ["learner_id", "signal_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_group_learning_signals_learner_type", table_name="group_learning_signals")
    op.drop_index("ix_group_learning_signals_learner_status", table_name="group_learning_signals")
    op.drop_index("ix_group_learning_signals_learner_id", table_name="group_learning_signals")
    op.drop_index("ix_group_learning_signals_message_id", table_name="group_learning_signals")
    op.drop_table("group_learning_signals")

    op.drop_index("ix_group_learning_messages_learner_status", table_name="group_learning_messages")
    op.drop_index("ix_group_learning_messages_source_occurred", table_name="group_learning_messages")
    op.drop_index("ix_group_learning_messages_learner_id", table_name="group_learning_messages")
    op.drop_index("ix_group_learning_messages_source_id", table_name="group_learning_messages")
    op.drop_table("group_learning_messages")

    op.drop_index("ix_group_learning_participants_learner", table_name="group_learning_participants")
    op.drop_index("ix_group_learning_participants_source_role", table_name="group_learning_participants")
    op.drop_index("ix_group_learning_participants_source_id", table_name="group_learning_participants")
    op.drop_table("group_learning_participants")

    op.drop_index("ix_group_learning_sources_learner_status", table_name="group_learning_sources")
    op.drop_index("ix_group_learning_sources_learner_id", table_name="group_learning_sources")
    op.drop_table("group_learning_sources")
