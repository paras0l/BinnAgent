"""add vocabulary learning and spelling

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-19 04:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_ID = "70000000-0000-4000-8000-000000000001"

SEED_WORDS = [
    (
        "73000000-0000-4000-8000-000000000001",
        "71000000-0000-4000-8000-000000000001",
        "good",
        "/ɡʊd/",
        "好的",
        "S1",
        True,
        "Good morning!",
    ),
    (
        "73000000-0000-4000-8000-000000000002",
        "71000000-0000-4000-8000-000000000001",
        "morning",
        "/ˈmɔːnɪŋ/",
        "早晨；上午",
        "S1",
        True,
        "Good morning!",
    ),
    (
        "73000000-0000-4000-8000-000000000003",
        "71000000-0000-4000-8000-000000000001",
        "hello",
        "/həˈləʊ/",
        "你好；喂",
        "S1",
        True,
        "Hello, Eric!",
    ),
    (
        "73000000-0000-4000-8000-000000000004",
        "71000000-0000-4000-8000-000000000001",
        "afternoon",
        "/ˌɑːftəˈnuːn/",
        "下午",
        "S3",
        True,
        "Good afternoon!",
    ),
    (
        "73000000-0000-4000-8000-000000000005",
        "71000000-0000-4000-8000-000000000001",
        "evening",
        "/ˈiːvnɪŋ/",
        "晚上；傍晚",
        "S3",
        True,
        "Good evening!",
    ),
    (
        "73000000-0000-4000-8000-000000000006",
        "71000000-0000-4000-8000-000000000001",
        "thanks",
        "/θæŋks/",
        "感谢；谢谢",
        "S3",
        True,
        "Fine, thanks.",
    ),
    (
        "73000000-0000-4000-8000-000000000007",
        "71000000-0000-4000-8000-000000000001",
        "fine",
        "/faɪn/",
        "健康的；美好的",
        "S3",
        True,
        "I'm fine, thanks.",
    ),
    (
        "73000000-0000-4000-8000-000000000008",
        "71000000-0000-4000-8000-000000000004",
        "name",
        "/neɪm/",
        "名字；名称",
        "1",
        True,
        "My name is Gina.",
    ),
    (
        "73000000-0000-4000-8000-000000000009",
        "71000000-0000-4000-8000-000000000004",
        "nice",
        "/naɪs/",
        "令人愉快的；宜人的",
        "1",
        True,
        "Nice to meet you.",
    ),
    (
        "73000000-0000-4000-8000-000000000010",
        "71000000-0000-4000-8000-000000000004",
        "meet",
        "/miːt/",
        "遇见；相逢",
        "1",
        True,
        "Nice to meet you.",
    ),
    (
        "73000000-0000-4000-8000-000000000011",
        "71000000-0000-4000-8000-000000000004",
        "friend",
        "/frend/",
        "朋友",
        "5",
        True,
        "She is my friend.",
    ),
    (
        "73000000-0000-4000-8000-000000000012",
        "71000000-0000-4000-8000-000000000004",
        "school",
        "/skuːl/",
        "学校",
        "6",
        True,
        "I am in a middle school.",
    ),
]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.add_column("vocabulary_items", sa.Column("canonical_key", sa.String(255), nullable=True))
    op.add_column(
        "vocabulary_items",
        sa.Column("entry_kind", sa.String(30), nullable=False, server_default="word"),
    )
    op.add_column(
        "vocabulary_items",
        sa.Column("preferred_accent", sa.String(10), nullable=False, server_default="auto"),
    )
    op.execute("UPDATE vocabulary_items SET canonical_key = lower(trim(word))")
    op.alter_column("vocabulary_items", "canonical_key", nullable=False)
    op.create_unique_constraint(
        "uq_vocabulary_learner_key", "vocabulary_items", ["learner_id", "canonical_key"]
    )

    op.create_table(
        "vocabulary_item_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_version_id", sa.String(255), nullable=True),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_label", sa.String(120), nullable=False),
        sa.Column(
            "context_snapshot",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "vocabulary_item_id",
            "source_type",
            "source_id",
            "curriculum_node_id",
            name="uq_vocabulary_item_source",
        ),
    )
    op.create_index(
        "ix_vocabulary_item_sources_learner_id", "vocabulary_item_sources", ["learner_id"]
    )
    op.create_index(
        "ix_vocabulary_item_sources_vocabulary_item_id",
        "vocabulary_item_sources",
        ["vocabulary_item_id"],
    )
    op.create_index(
        "ix_vocabulary_item_sources_curriculum_node_id",
        "vocabulary_item_sources",
        ["curriculum_node_id"],
    )
    op.create_index(
        "ix_vocabulary_sources_learner_type",
        "vocabulary_item_sources",
        ["learner_id", "source_type"],
    )

    op.create_table(
        "vocabulary_practice_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("prompt_mode", sa.String(30), nullable=False, server_default="audio"),
        sa.Column("accent", sa.String(10), nullable=False, server_default="uk"),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column(
            "item_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("current_index", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("correct_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("hinted_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("revealed_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_vocabulary_practice_sessions_learner_id", "vocabulary_practice_sessions", ["learner_id"]
    )
    op.create_index(
        "ix_vocabulary_practice_sessions_curriculum_node_id",
        "vocabulary_practice_sessions",
        ["curriculum_node_id"],
    )
    op.create_index(
        "ix_vocabulary_sessions_learner_status",
        "vocabulary_practice_sessions",
        ["learner_id", "status"],
    )

    op.create_table(
        "vocabulary_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("drill_type", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("normalized_answer", sa.Text, nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(30), nullable=True),
        sa.Column(
            "letter_diff", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("hint_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("replay_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["session_id"], ["vocabulary_practice_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "session_id", "idempotency_key", name="uq_vocabulary_attempt_idempotency"
        ),
    )
    op.create_index("ix_vocabulary_attempts_session_id", "vocabulary_attempts", ["session_id"])
    op.create_index("ix_vocabulary_attempts_learner_id", "vocabulary_attempts", ["learner_id"])
    op.create_index(
        "ix_vocabulary_attempts_vocabulary_item_id", "vocabulary_attempts", ["vocabulary_item_id"]
    )
    op.create_index(
        "ix_vocabulary_attempts_learner_item",
        "vocabulary_attempts",
        ["learner_id", "vocabulary_item_id"],
    )

    for point_id, node_id, word, phonetic, meaning, page, is_key, example in SEED_WORDS:
        op.execute(
            sa.text("""
                INSERT INTO knowledge_points
                  (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
                   source_page, difficulty, status, content)
                VALUES
                  (CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid),
                   :canonical_key, 'vocabulary', :word, :meaning, :source_page, 0.2,
                   'published', CAST(:content AS jsonb))
                ON CONFLICT (canonical_key) DO NOTHING
            """).bindparams(
                id=point_id,
                source_id=SOURCE_ID,
                node_id=node_id,
                canonical_key=f"vocabulary.{word.replace(' ', '-')}.seed",
                word=word,
                meaning=meaning,
                source_page=f"P.{page}",
                content=(
                    '{"origin":"verified_seed","role":"unit_wordlist",'
                    f'"lemma":"{word}","entry_kind":"word","phonetic":"{phonetic}",'
                    f'"definitions_zh":["{meaning}"],"examples":["{example}"],'
                    f'"is_key_vocabulary":{str(is_key).lower()},"lesson_printed_page":"{page}"}}'
                ),
            )
        )
    op.execute(
        sa.text("""
            UPDATE knowledge_sources
            SET knowledge_count = (
                SELECT count(*) FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid)
            )
            WHERE id = CAST(:source_id AS uuid)
        """).bindparams(source_id=SOURCE_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM knowledge_points WHERE id = ANY(CAST(:ids AS uuid[]))").bindparams(
            ids=[item[0] for item in SEED_WORDS]
        )
    )
    op.drop_table("vocabulary_attempts")
    op.drop_table("vocabulary_practice_sessions")
    op.drop_table("vocabulary_item_sources")
    op.drop_constraint("uq_vocabulary_learner_key", "vocabulary_items", type_="unique")
    op.drop_column("vocabulary_items", "preferred_accent")
    op.drop_column("vocabulary_items", "entry_kind")
    op.drop_column("vocabulary_items", "canonical_key")
