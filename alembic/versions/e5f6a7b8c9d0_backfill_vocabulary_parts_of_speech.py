"""backfill vocabulary parts of speech

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-19 06:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARTS_OF_SPEECH = {
    "good": "adj.",
    "morning": "n.",
    "hello": "interj.",
    "afternoon": "n.",
    "evening": "n.",
    "thanks": "interj.",
    "fine": "adj.",
    "name": "n.",
    "nice": "adj.",
    "meet": "v.",
    "friend": "n.",
    "school": "n.",
}


def upgrade() -> None:
    for word, part_of_speech in PARTS_OF_SPEECH.items():
        op.execute(
            sa.text("""
                UPDATE knowledge_points
                SET content = jsonb_set(
                    COALESCE(content, '{}'::jsonb),
                    '{part_of_speech}',
                    to_jsonb(CAST(:part_of_speech AS text)),
                    true
                )
                WHERE canonical_key = :canonical_key
            """).bindparams(
                canonical_key=f"vocabulary.{word}.seed",
                part_of_speech=part_of_speech,
            )
        )
    op.execute(
        sa.text("""
        UPDATE vocabulary_items AS item
        SET meanings = jsonb_build_array(jsonb_build_object(
            'part_of_speech', point.content->>'part_of_speech',
            'definition_zh', point.summary
        ))
        FROM vocabulary_item_sources AS source
        JOIN knowledge_points AS point ON source.source_id = CAST(point.id AS text)
        WHERE source.vocabulary_item_id = item.id
          AND source.source_type = 'textbook_unit'
          AND point.canonical_key LIKE 'vocabulary.%.seed'
          AND point.content ? 'part_of_speech'
    """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
        UPDATE vocabulary_items AS item
        SET meanings = jsonb_build_array(point.summary)
        FROM vocabulary_item_sources AS source
        JOIN knowledge_points AS point ON source.source_id = CAST(point.id AS text)
        WHERE source.vocabulary_item_id = item.id
          AND source.source_type = 'textbook_unit'
          AND point.canonical_key LIKE 'vocabulary.%.seed'
    """)
    )
    op.execute(
        sa.text("""
        UPDATE knowledge_points
        SET content = content - 'part_of_speech'
        WHERE canonical_key LIKE 'vocabulary.%.seed'
    """)
    )
