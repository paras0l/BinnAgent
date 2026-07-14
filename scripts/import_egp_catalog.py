#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from src.db import async_session_factory
from src.grammar.egp_catalog import (
    CATALOG_VERSION,
    EGP_ACKNOWLEDGEMENT,
    EGP_CITATION,
    EGP_SOURCE_URL,
    EXPECTED_ENTRY_COUNT,
    EGPCatalog,
    load_egp_catalog,
)
from src.models.knowledge import GrammarCanDoProfile, KnowledgePoint


NAMESPACE = uuid.UUID("53bdfc82-92d5-4d87-9d59-57cbfd31197a")
DIFFICULTY_BY_CEFR = {"A1": 0.2, "A2": 0.35, "B1": 0.5, "B2": 0.65, "C1": 0.8, "C2": 0.9}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import an authorised English Grammar Profile XLSX/CSV export.")
    parser.add_argument("path", type=Path, help="Path to the authorised egponline.csv export")
    parser.add_argument("--validate-only", action="store_true", help="Validate the 1,211-entry selection without writing to PostgreSQL")
    parser.add_argument("--manifest", type=Path, help="Write a non-content aggregate manifest")
    return parser


def _manifest(catalog: EGPCatalog) -> dict:
    levels: dict[str, int] = {}
    categories: dict[str, int] = {}
    example_count = 0
    for entry in catalog.entries:
        levels[entry.cefr_level] = levels.get(entry.cefr_level, 0) + 1
        categories[entry.super_category] = categories.get(entry.super_category, 0) + 1
        example_count += len(entry.examples)
    return {
        "catalog_version": CATALOG_VERSION,
        "entry_count": len(catalog.entries),
        "example_count": example_count,
        "source_row_count": catalog.source_row_count,
        "rows_with_examples": catalog.rows_with_examples,
        "selection_rule": "non-empty can-do and example containing CEFR A1-C2 learner metadata",
        "excluded_row_count": catalog.exclusion_count,
        "source_sha256": catalog.source_sha256,
        "source_url": EGP_SOURCE_URL,
        "citation": EGP_CITATION,
        "levels": dict(sorted(levels.items())),
        "categories": dict(sorted(categories.items())),
    }


async def _import(catalog: EGPCatalog) -> None:
    async with async_session_factory() as db:
        for entry in catalog.entries:
            point_id = uuid.uuid5(NAMESPACE, f"egp:{entry.external_id}")
            canonical_key = f"grammar.egp.{entry.external_id}"
            point_values = {
                "id": point_id,
                "source_id": None,
                "curriculum_node_id": None,
                "canonical_key": canonical_key,
                "type": "grammar_can_do",
                "title": entry.guideword or entry.can_do_statement.removesuffix("."),
                "summary": entry.can_do_statement,
                "source_page": f"egp:{entry.external_id}",
                "difficulty": DIFFICULTY_BY_CEFR[entry.cefr_level],
                "status": "published",
                "content": {
                    "source": "english_grammar_profile",
                    "external_id": entry.external_id,
                    "catalog_version": CATALOG_VERSION,
                },
            }
            point_stmt = insert(KnowledgePoint).values(**point_values)
            await db.execute(
                point_stmt.on_conflict_do_update(
                    constraint="uq_knowledge_points_canonical_key",
                    set_={key: value for key, value in point_values.items() if key not in {"id", "canonical_key"}},
                )
            )
            profile_values = {
                "id": uuid.uuid5(NAMESPACE, f"egp-profile:{entry.external_id}"),
                "knowledge_point_id": point_id,
                "external_id": entry.external_id,
                "category": entry.super_category,
                "subcategory": entry.sub_category,
                "cefr_level": entry.cefr_level,
                "construct_type": entry.construct_type,
                "guideword": entry.guideword,
                "lexical_range": entry.lexical_range,
                "can_do_statement": entry.can_do_statement,
                "success_criteria": ["目标语法结构在语境中正确实现", "形式、意义和语用符合该 can-do"],
                "failure_criteria": ["学习者尝试了目标结构但未正确实现", "修正句引入了原句缺失的目标结构"],
                "positive_examples": entry.examples,
                "negative_examples": [],
                "prerequisites": [],
                "detection_hints": {
                    "assessment_modes": ["recognition", "recall", "production"],
                    "requires_semantic_check": entry.construct_type != "FORM",
                },
                "catalog_version": CATALOG_VERSION,
                "source_url": EGP_SOURCE_URL,
                "source_attribution": EGP_ACKNOWLEDGEMENT,
            }
            profile_stmt = insert(GrammarCanDoProfile).values(**profile_values)
            await db.execute(
                profile_stmt.on_conflict_do_update(
                    constraint="uq_grammar_can_do_profile_point",
                    set_={key: value for key, value in profile_values.items() if key not in {"id", "knowledge_point_id"}},
                )
            )

        await db.execute(
            update(KnowledgePoint)
            .where(KnowledgePoint.canonical_key.like("grammar.g7.v1.%"))
            .values(status="archived")
        )
        await db.commit()


async def main() -> None:
    args = _parser().parse_args()
    catalog = load_egp_catalog(args.path, expected_count=EXPECTED_ENTRY_COUNT)
    manifest = _manifest(catalog)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.validate_only:
        await _import(catalog)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
