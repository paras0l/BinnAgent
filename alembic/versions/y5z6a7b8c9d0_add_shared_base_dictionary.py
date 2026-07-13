"""add shared base dictionary

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "base_dictionary_builds",
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("selection_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("statistics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_table(
        "base_dictionary_entries",
        sa.Column("canonical_key", sa.String(length=255), nullable=False),
        sa.Column("lemma", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("entry_kind", sa.String(length=32), nullable=False),
        sa.Column("frequency_zipf", sa.Float(), nullable=False),
        sa.Column("frequency_rank", sa.Integer(), nullable=False),
        sa.Column("parts_of_speech", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pronunciations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("forms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("senses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_attribution", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("build_version", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key", "entry_kind", name="uq_base_dictionary_key_kind"),
    )
    op.create_index("ix_base_dictionary_frequency_rank", "base_dictionary_entries", ["frequency_rank"])
    op.create_index(
        "ix_base_dictionary_kind_rank", "base_dictionary_entries", ["entry_kind", "frequency_rank"]
    )
    op.create_index(
        "ix_base_dictionary_active_key", "base_dictionary_entries", ["active", "canonical_key"]
    )
    op.create_table(
        "base_dictionary_translations",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sense_key", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("generator", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("source_definition_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["base_dictionary_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id", "sense_key", "locale", name="uq_base_dictionary_translation_sense"
        ),
    )
    op.create_index(
        "ix_base_dictionary_translation_entry",
        "base_dictionary_translations",
        ["entry_id", "locale"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_base_dictionary_translation_entry", table_name="base_dictionary_translations"
    )
    op.drop_table("base_dictionary_translations")
    op.drop_index("ix_base_dictionary_active_key", table_name="base_dictionary_entries")
    op.drop_index("ix_base_dictionary_kind_rank", table_name="base_dictionary_entries")
    op.drop_index("ix_base_dictionary_frequency_rank", table_name="base_dictionary_entries")
    op.drop_table("base_dictionary_entries")
    op.drop_table("base_dictionary_builds")
