#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db import async_session_factory  # noqa: E402
from src.models.knowledge import CurriculumNode, KnowledgePoint  # noqa: E402
from src.models.learner import Learner  # noqa: E402
from src.models.vocabulary import VocabularyItem, VocabularyItemSource  # noqa: E402
from src.tools.free_dictionary import (  # noqa: E402
    FreeDictionaryEntry,
    lookup_free_dictionary,
)
from src.tools.vocabulary_enrichment import (  # noqa: E402
    LocalVocabularyEntry,
    enrich_vocabulary_with_local_model,
)
from src.vocabulary.learning import _entry_kind, canonical_vocabulary_key  # noqa: E402

TEXTBOOK_SOURCE_ID = "70000000-0000-4000-8000-000000000001"
CONFIRM_TOKEN = "OVERWRITE_TEXTBOOK_VOCABULARY"


@dataclass(frozen=True)
class PreparedEntry:
    expression: str
    canonical_key: str
    point_id: uuid.UUID
    source_id: uuid.UUID
    curriculum_node_id: uuid.UUID
    source_page: str | None
    unit_order: int | None
    pronunciation: FreeDictionaryEntry
    enrichment: LocalVocabularyEntry


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh textbook vocabulary with Free Dictionary pronunciation/audio "
            "and local-model semantic enrichment without partial writes."
        )
    )
    parser.add_argument("--limit", type=int, default=30, help="Number of sequence entries.")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Zero-based sequence offset, useful for resumable batches.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Required to write changes: {CONFIRM_TOKEN}",
    )
    parser.add_argument(
        "--learner-id",
        type=uuid.UUID,
        help="Learner to upsert vocabulary for. Without it, only existing rows are overwritten.",
    )
    return parser.parse_args(argv)


async def ordered_points(db: AsyncSession, limit: int, offset: int = 0) -> list[KnowledgePoint]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if offset < 0:
        raise ValueError("offset must not be negative")
    result = await db.execute(
        select(KnowledgePoint)
        .join(CurriculumNode, CurriculumNode.id == KnowledgePoint.curriculum_node_id)
        .where(
            KnowledgePoint.source_id == TEXTBOOK_SOURCE_ID,
            KnowledgePoint.type == "vocabulary",
            KnowledgePoint.status == "published",
            KnowledgePoint.content["role"].as_string() == "unit_wordlist",
        )
        .order_by(
            CurriculumNode.ordinal.asc(),
            KnowledgePoint.content["unit_order"].as_integer().asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def prepare_entries(points: list[KnowledgePoint]) -> list[PreparedEntry]:
    prepared: list[PreparedEntry] = []
    for index, point in enumerate(points, start=1):
        expression = point.title
        pronunciation = await lookup_free_dictionary(expression)
        enrichment = await enrich_vocabulary_with_local_model(expression, pronunciation)
        prepared.append(
            PreparedEntry(
                expression=expression,
                canonical_key=canonical_vocabulary_key(
                    str((point.content or {}).get("lemma") or expression)
                ),
                point_id=point.id,
                source_id=point.source_id,
                curriculum_node_id=point.curriculum_node_id,
                source_page=point.source_page,
                unit_order=(point.content or {}).get("unit_order"),
                pronunciation=pronunciation,
                enrichment=enrichment,
            )
        )
        print(f"fetched {index}/{len(points)}: {expression}")
    return prepared


def apply_entry(item: VocabularyItem, entry: PreparedEntry) -> None:
    item.word = entry.expression
    item.phonetic = (
        entry.pronunciation.phonetic_uk
        or entry.pronunciation.phonetic_us
        or entry.pronunciation.phonetic
    )
    item.phonetic_uk = entry.pronunciation.phonetic_uk
    item.phonetic_us = entry.pronunciation.phonetic_us
    item.audio_url = entry.pronunciation.audio_url
    item.audio_uk = entry.pronunciation.audio_uk
    item.audio_us = entry.pronunciation.audio_us
    item.meanings = entry.enrichment.meanings
    item.dictionary_senses = entry.enrichment.dictionary_senses
    item.word_forms = entry.enrichment.word_forms
    item.dictionary_tags = entry.enrichment.dictionary_tags
    item.examples = entry.enrichment.examples
    item.collocations = entry.enrichment.collocations
    item.dictionary_provider = f"{entry.pronunciation.provider}+{entry.enrichment.provider}"
    item.dictionary_enriched_at = datetime.now(timezone.utc)


async def _ensure_learner(db: AsyncSession, learner_id: uuid.UUID | None) -> None:
    if learner_id is None:
        return
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise RuntimeError(f"learner not found: {learner_id}")


async def overwrite_entries(
    db: AsyncSession, entries: list[PreparedEntry], learner_id: uuid.UUID | None = None
) -> int:
    await _ensure_learner(db, learner_id)
    keys = [entry.canonical_key for entry in entries]
    item_query = select(VocabularyItem).where(VocabularyItem.canonical_key.in_(keys))
    if learner_id is not None:
        item_query = item_query.where(VocabularyItem.learner_id == learner_id)
    result = await db.execute(item_query.with_for_update())
    items = list(result.scalars().all())
    entry_by_key = {entry.canonical_key: entry for entry in entries}
    items_by_key = {item.canonical_key: item for item in items}
    if learner_id is not None:
        for entry in entries:
            if entry.canonical_key in items_by_key:
                continue
            item = VocabularyItem(
                learner_id=learner_id,
                word=entry.expression,
                canonical_key=entry.canonical_key,
                entry_kind=_entry_kind(entry.expression),
                preferred_accent="auto",
                level="grade-7",
                source_ref=f"knowledge:{entry.point_id}",
                status="learning",
                confidence=0.0,
                review_count=0,
                next_review_at=datetime.now(timezone.utc),
            )
            db.add(item)
            items.append(item)
            items_by_key[entry.canonical_key] = item
    for item in items:
        apply_entry(item, entry_by_key[item.canonical_key])
    await db.flush()

    item_ids = [item.id for item in items]
    if not item_ids:
        return 0
    existing_source_result = await db.execute(
        select(VocabularyItemSource).where(
            VocabularyItemSource.vocabulary_item_id.in_(item_ids),
            VocabularyItemSource.source_type == "textbook_unit",
        )
    )
    existing_sources = {
        (source.vocabulary_item_id, source.source_id): source
        for source in existing_source_result.scalars().all()
    }
    for item in items:
        entry = entry_by_key[item.canonical_key]
        source_key = (item.id, str(entry.point_id))
        source = existing_sources.get(source_key)
        if source is None and learner_id is not None:
            source = VocabularyItemSource(
                learner_id=learner_id,
                vocabulary_item_id=item.id,
                source_type="textbook_unit",
                source_id=str(entry.point_id),
                source_version_id=str(entry.source_id),
                curriculum_node_id=entry.curriculum_node_id,
                display_label="七上 · 教材词汇",
                context_snapshot={},
                active=True,
            )
            db.add(source)
        if source is None:
            continue
        context = dict(source.context_snapshot or {})
        context["source_page"] = entry.source_page
        context["unit_order"] = entry.unit_order
        context["dictionary_provider"] = item.dictionary_provider
        source.context_snapshot = context
    await db.flush()
    return len(items)


async def run(*, limit: int, offset: int, apply: bool, learner_id: uuid.UUID | None) -> int:
    async with async_session_factory() as db:
        points = await ordered_points(db, limit, offset)
        if len(points) != limit:
            raise RuntimeError(f"requested {limit} entries but found {len(points)}")
        print(
            f"sequence positions {offset + 1}-{offset + len(points)}: "
            + ", ".join(point.title for point in points)
        )
        if not apply:
            print(f"dry run only; pass --confirm {CONFIRM_TOKEN} to fetch and overwrite")
            return 0

    # Network work happens before the write transaction. A failed lookup changes no rows.
    entries = await prepare_entries(points)
    async with async_session_factory.begin() as db:
        updated = await overwrite_entries(db, entries, learner_id)
    print(f"committed: sequence_entries={len(entries)} vocabulary_rows={updated}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(
        run(
            limit=args.limit,
            offset=args.offset,
            apply=args.confirm == CONFIRM_TOKEN,
            learner_id=args.learner_id,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
