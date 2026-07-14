"""add idempotent agent learning evidence events

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a4
"""

from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b5"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ATOMIC_KCS = [
    (
        "grammar.reported_question.word_order",
        "grammar_atomic",
        "间接疑问句使用陈述语序",
        "whether、if 或 wh-word 引导的间接疑问从句使用陈述语序。",
    ),
    (
        "grammar.reported_speech.backshift",
        "grammar_atomic",
        "间接引语中的时态后移",
        "在相关语境中把 will/can/may 等形式后移为 would/could/might。",
    ),
    (
        "vocabulary.collocation.make_a_decision",
        "vocabulary_atomic",
        "make a decision 搭配",
        "使用 make a decision，而不是 do a decision。",
    ),
]


def upgrade() -> None:
    op.create_table(
        "learning_evidence_events",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("question_id", sa.String(255), nullable=True),
        sa.Column("observations", postgresql.JSONB(), nullable=False),
        sa.Column("raw_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("matcher_model_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "event_id", name="uq_learning_evidence_event"),
    )
    op.create_index(
        "ix_learning_evidence_event_learner",
        "learning_evidence_events",
        ["learner_id", "created_at"],
    )
    namespace = uuid.UUID("f3402969-7651-42db-8ef8-4a9c0f3778ad")
    for canonical_key, point_type, title, summary in ATOMIC_KCS:
        op.execute(
            sa.text(
                """
                INSERT INTO knowledge_points
                    (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
                     source_page, difficulty, status, content)
                VALUES
                    (CAST(:id AS uuid), NULL, NULL, :canonical_key, :type, :title, :summary,
                     'agent-tools:v1', 0.5, 'published', CAST(:content AS jsonb))
                ON CONFLICT (canonical_key) DO NOTHING
                """
            ).bindparams(
                id=str(uuid.uuid5(namespace, canonical_key)),
                canonical_key=canonical_key,
                type=point_type,
                title=title,
                summary=summary,
                content=json.dumps({"atomic_kc": True, "catalog_version": "agent-tools-v1"}),
            )
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM knowledge_points WHERE canonical_key IN "
        "('grammar.reported_question.word_order', "
        "'grammar.reported_speech.backshift', "
        "'vocabulary.collocation.make_a_decision')"
    )
    op.drop_index("ix_learning_evidence_event_learner", table_name="learning_evidence_events")
    op.drop_table("learning_evidence_events")
