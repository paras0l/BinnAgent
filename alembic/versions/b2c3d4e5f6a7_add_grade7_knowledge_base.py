"""add grade 7 knowledge base

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-18 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("owner_learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("edition", sa.String(100), nullable=True),
        sa.Column("grade", sa.String(30), nullable=False),
        sa.Column("volume", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("object_key", sa.String(1000), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("unit_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("knowledge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["owner_learner_id"], ["learners.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_knowledge_sources_owner_learner_id", "knowledge_sources", ["owner_learner_id"]
    )
    op.create_index("ix_knowledge_sources_grade", "knowledge_sources", ["grade"])

    op.create_table(
        "curriculum_nodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("node_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subtitle", sa.String(255), nullable=True),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("start_page", sa.String(30), nullable=True),
        sa.Column("end_page", sa.String(30), nullable=True),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=True),
        sa.Column(
            "learning_objectives",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["curriculum_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "source_id", "parent_id", "ordinal", name="uq_curriculum_source_parent_ordinal"
        ),
    )
    op.create_index("ix_curriculum_nodes_source_id", "curriculum_nodes", ["source_id"])
    op.create_index("ix_curriculum_nodes_parent_id", "curriculum_nodes", ["parent_id"])

    op.create_table(
        "knowledge_points",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_key", sa.String(255), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_page", sa.String(30), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column(
            "content", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("canonical_key", name="uq_knowledge_points_canonical_key"),
    )
    op.create_index("ix_knowledge_points_source_id", "knowledge_points", ["source_id"])
    op.create_index(
        "ix_knowledge_points_curriculum_node_id", "knowledge_points", ["curriculum_node_id"]
    )
    op.create_index("ix_knowledge_points_type", "knowledge_points", ["type"])

    op.create_table(
        "learner_knowledge_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="learning"),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("exposure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence_summary",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("learner_id", "knowledge_point_id", name="uq_learner_knowledge_state"),
    )
    op.create_index(
        "ix_learner_knowledge_states_learner_id", "learner_knowledge_states", ["learner_id"]
    )
    op.create_index(
        "ix_learner_knowledge_states_knowledge_point_id",
        "learner_knowledge_states",
        ["knowledge_point_id"],
    )
    op.create_index(
        "ix_learner_knowledge_review", "learner_knowledge_states", ["learner_id", "next_review_at"]
    )

    op.create_table(
        "knowledge_learning_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_knowledge_learning_events_learner_id", "knowledge_learning_events", ["learner_id"]
    )
    op.create_index(
        "ix_knowledge_learning_events_session_id", "knowledge_learning_events", ["session_id"]
    )
    op.create_index(
        "ix_knowledge_learning_events_knowledge_point_id",
        "knowledge_learning_events",
        ["knowledge_point_id"],
    )

    source_id = "70000000-0000-4000-8000-000000000001"
    nodes = [
        (
            "71000000-0000-4000-8000-000000000001",
            "Starter Unit 1",
            "Good morning!",
            1,
            "S1",
            "S4",
            20,
        ),
        (
            "71000000-0000-4000-8000-000000000002",
            "Starter Unit 2",
            "What's this in English?",
            2,
            "S5",
            "S8",
            20,
        ),
        (
            "71000000-0000-4000-8000-000000000003",
            "Starter Unit 3",
            "What color is it?",
            3,
            "S9",
            "S12",
            20,
        ),
        ("71000000-0000-4000-8000-000000000004", "Unit 1", "My name's Gina.", 4, "1", "6", 30),
        ("71000000-0000-4000-8000-000000000005", "Unit 2", "This is my sister.", 5, "7", "12", 30),
    ]
    op.execute(
        sa.text("""
        INSERT INTO knowledge_sources
          (id, title, filename, publisher, edition, grade, volume, status, visibility,
           sha256, file_size, page_count, unit_count, knowledge_count, metadata)
        VALUES
          (CAST(:id AS uuid), '英语 七年级上册', '义务教育教科书·英语七年级上册.pdf',
           '人民教育出版社（PEP）', '人教版', 'grade-7', 'upper', 'published', 'public',
           :sha, 12005272, 138, 12, 428, '{"seed": true, "schema_version": "1"}'::jsonb)
    """).bindparams(id=source_id, sha="7" * 64)
    )
    for node_id, title, subtitle, ordinal, start_page, end_page, minutes in nodes:
        op.execute(
            sa.text("""
            INSERT INTO curriculum_nodes
              (id, source_id, node_type, title, subtitle, ordinal, start_page, end_page,
               estimated_minutes, learning_objectives)
            VALUES
              (CAST(:id AS uuid), CAST(:source_id AS uuid), 'unit', :title, :subtitle,
               :ordinal, :start_page, :end_page,
               :minutes, '[]'::jsonb)
        """).bindparams(
                id=node_id,
                source_id=source_id,
                title=title,
                subtitle=subtitle,
                ordinal=ordinal,
                start_page=start_page,
                end_page=end_page,
                minutes=minutes,
            )
        )

    points = [
        (
            "72000000-0000-4000-8000-000000000001",
            "phrase.good-morning",
            "phrase",
            "Good morning!",
            "用于早晨向他人问好。",
            "P.2",
            0.15,
        ),
        (
            "72000000-0000-4000-8000-000000000002",
            "pattern.how-are-you",
            "sentence_pattern",
            "How are you?",
            "用于询问对方的近况。",
            "P.2",
            0.2,
        ),
        (
            "72000000-0000-4000-8000-000000000003",
            "vocabulary.letters-a-h",
            "vocabulary",
            "Letters A–H",
            "字母 A 到 H 的读音与书写。",
            "P.3–4",
            0.1,
        ),
        (
            "72000000-0000-4000-8000-000000000004",
            "pattern.im-fine-thanks",
            "sentence_pattern",
            "I'm fine, thanks.",
            "用于回复对方的问候。",
            "P.2",
            0.2,
        ),
    ]
    for point in points:
        op.execute(
            sa.text("""
            INSERT INTO knowledge_points
              (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
               source_page, difficulty, status, content)
            VALUES
              (CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid),
               :key, :type, :title, :summary,
               :source_page, :difficulty, 'published', '{}'::jsonb)
        """).bindparams(
                id=point[0],
                source_id=source_id,
                node_id=nodes[0][0],
                key=point[1],
                type=point[2],
                title=point[3],
                summary=point[4],
                source_page=point[5],
                difficulty=point[6],
            )
        )


def downgrade() -> None:
    op.drop_table("knowledge_learning_events")
    op.drop_index("ix_learner_knowledge_review", table_name="learner_knowledge_states")
    op.drop_table("learner_knowledge_states")
    op.drop_table("knowledge_points")
    op.drop_table("curriculum_nodes")
    op.drop_table("knowledge_sources")
