"""add parser review items

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-07-03 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parser_review_items",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parser_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issue_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_fix", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parser_run_id"], ["parser_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_learner_id"], ["learners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parser_review_items_decision",
        "parser_review_items",
        ["decision"],
    )
    op.create_index(
        "ix_parser_review_items_issue_type",
        "parser_review_items",
        ["issue_type"],
    )
    op.create_index(
        "ix_parser_review_items_parser_run_id",
        "parser_review_items",
        ["parser_run_id"],
    )
    op.create_index(
        "ix_parser_review_items_severity",
        "parser_review_items",
        ["severity"],
    )
    op.create_index(
        "ix_parser_review_items_source_id",
        "parser_review_items",
        ["source_id"],
    )
    op.create_index(
        "ix_parser_review_items_target_id",
        "parser_review_items",
        ["target_id"],
    )
    op.create_index(
        "ix_parser_review_items_target_type",
        "parser_review_items",
        ["target_type"],
    )
    op.create_index(
        "ix_parser_review_items_reviewed_by_learner_id",
        "parser_review_items",
        ["reviewed_by_learner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_parser_review_items_reviewed_by_learner_id", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_target_type", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_target_id", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_source_id", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_severity", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_parser_run_id", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_issue_type", table_name="parser_review_items")
    op.drop_index("ix_parser_review_items_decision", table_name="parser_review_items")
    op.drop_table("parser_review_items")
