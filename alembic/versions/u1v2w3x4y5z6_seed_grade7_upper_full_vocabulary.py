"""seed complete grade 7 upper vocabulary catalog

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-07-11 13:00:00.000000
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_ID = "c7000000-0000-4000-8000-000000000001"
NAMESPACE = uuid.UUID("8fe269df-9361-4d0c-b2c9-63ea36f197aa")
CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "classroom"
    / "assets"
    / "pep_grade7_upper_2024"
    / "catalog.json"
)


def upgrade() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    connection = op.get_bind()
    total = 0
    for unit in catalog["units"]:
        ordinal = int(unit["ordinal"])
        node_id = f"c71{ordinal:02d}000-0000-4000-8000-000000000001"
        groups = (
            ("core", unit["vocabulary"], "unit_wordlist", catalog["source_files"]["core_vocabulary"]),
            (
                "primary_review",
                unit["primary_review_vocabulary"],
                "primary_review_wordlist",
                catalog["source_files"]["primary_vocabulary"],
            ),
        )
        unit_order = 0
        for band, entries, role, source_file in groups:
            for entry in entries:
                unit_order += 1
                stable_key = f"changsha-pep-grade7-upper-2024:unit:{ordinal:02d}:vocabulary:{band}:{unit_order:03d}"
                point_id = uuid.uuid5(NAMESPACE, stable_key)
                content = {
                    "role": role,
                    "origin": "curated_markdown_catalog",
                    "stable_key": stable_key,
                    "lemma": entry["term"],
                    "definition_zh": entry.get("meaning_zh"),
                    "phonetic": entry.get("phonetic"),
                    "part_of_speech": entry.get("part_of_speech"),
                    "entry_kind": "review_word" if band == "primary_review" else "word",
                    "vocabulary_band": band,
                    "unit_order": unit_order,
                    "source_file": source_file,
                    "confidence": 1.0,
                    "requires_review": False,
                    "copyright_note": "Structured vocabulary facts derived from the user-provided textbook materials",
                }
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO knowledge_points
                          (id, source_id, curriculum_node_id, canonical_key, type, title,
                           summary, source_page, difficulty, status, content)
                        VALUES
                          (:id, CAST(:source_id AS uuid), CAST(:node_id AS uuid), :canonical_key,
                           'vocabulary', :title, :summary, :source_page, :difficulty, 'published',
                           CAST(:content AS jsonb))
                        ON CONFLICT (id) DO UPDATE SET
                          title = EXCLUDED.title,
                          summary = EXCLUDED.summary,
                          source_page = EXCLUDED.source_page,
                          status = 'published',
                          content = EXCLUDED.content
                        """
                    ).bindparams(
                        id=point_id,
                        source_id=SOURCE_ID,
                        node_id=node_id,
                        canonical_key=stable_key,
                        title=entry["term"],
                        summary=entry.get("meaning_zh") or entry["term"],
                        source_page=(
                            f"p.{entry['printed_page']}"
                            if entry.get("printed_page")
                            else "Vocabulary from Primary School"
                        ),
                        difficulty=0.12 if band == "primary_review" else 0.22,
                        content=json.dumps(content, ensure_ascii=False),
                    )
                )
                total += 1
    connection.execute(
        sa.text(
            "UPDATE knowledge_sources SET knowledge_count = knowledge_count + :total "
            "WHERE id = CAST(:source_id AS uuid)"
        ).bindparams(total=total, source_id=SOURCE_ID)
    )


def downgrade() -> None:
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "DELETE FROM knowledge_points "
            "WHERE source_id = CAST(:source_id AS uuid) "
            "AND canonical_key LIKE 'changsha-pep-grade7-upper-2024:unit:%:vocabulary:%'"
        ).bindparams(source_id=SOURCE_ID)
    )
    connection.execute(
        sa.text(
            "UPDATE knowledge_sources SET knowledge_count = GREATEST(0, knowledge_count - :total) "
            "WHERE id = CAST(:source_id AS uuid)"
        ).bindparams(total=result.rowcount or 0, source_id=SOURCE_ID)
    )
