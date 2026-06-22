#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import sys
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
from src.models.vocabulary import VocabularyItem  # noqa: E402
from src.tools.baidu_dictionary import (  # noqa: E402
    BaiduDictionaryEntry,
    lookup_baidu_dictionary,
)
from src.tools.free_dictionary import (  # noqa: E402
    FreeDictionaryEntry,
    lookup_free_dictionary,
)
from src.vocabulary.learning import canonical_vocabulary_key  # noqa: E402

TEXTBOOK_SOURCE_ID = "70000000-0000-4000-8000-000000000001"
CONFIRM_TOKEN = "OVERWRITE_TEXTBOOK_VOCABULARY"


@dataclass(frozen=True)
class PreparedEntry:
    expression: str
    canonical_key: str
    base: FreeDictionaryEntry
    rich: BaiduDictionaryEntry


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh textbook vocabulary from Baidu Dictionary without partial writes."
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
        rich = await lookup_baidu_dictionary(expression)
        base = await lookup_free_dictionary(expression)
        prepared.append(
            PreparedEntry(
                expression=expression,
                canonical_key=canonical_vocabulary_key(
                    str((point.content or {}).get("lemma") or expression)
                ),
                base=base,
                rich=rich,
            )
        )
        print(f"fetched {index}/{len(points)}: {expression}")
    return prepared


def apply_entry(item: VocabularyItem, entry: PreparedEntry) -> None:
    item.word = entry.expression
    item.phonetic = entry.rich.phonetic_uk or entry.rich.phonetic_us or entry.base.phonetic
    item.phonetic_uk = entry.rich.phonetic_uk
    item.phonetic_us = entry.rich.phonetic_us
    item.meanings = entry.base.meanings
    item.dictionary_senses = entry.rich.senses
    item.word_forms = entry.rich.word_forms
    item.dictionary_tags = entry.rich.tags
    item.examples = entry.base.examples
    item.collocations = []
    item.dictionary_provider = f"{entry.rich.provider}+{entry.base.provider}"
    item.dictionary_enriched_at = datetime.now(timezone.utc)


async def overwrite_entries(db: AsyncSession, entries: list[PreparedEntry]) -> int:
    keys = [entry.canonical_key for entry in entries]
    result = await db.execute(
        select(VocabularyItem).where(VocabularyItem.canonical_key.in_(keys)).with_for_update()
    )
    items = list(result.scalars().all())
    entry_by_key = {entry.canonical_key: entry for entry in entries}
    for item in items:
        apply_entry(item, entry_by_key[item.canonical_key])
    await db.flush()
    return len(items)


async def run(*, limit: int, offset: int, apply: bool) -> int:
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
        updated = await overwrite_entries(db, entries)
    print(f"committed: sequence_entries={len(entries)} vocabulary_rows={updated}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(
        run(
            limit=args.limit,
            offset=args.offset,
            apply=args.confirm == CONFIRM_TOKEN,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
