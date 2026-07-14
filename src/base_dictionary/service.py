from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base_dictionary.pipeline import canonical_key
from src.models.base_dictionary import BaseDictionaryEntry, BaseDictionaryTranslation


async def get_entry(db: AsyncSession, term: str) -> dict | None:
    key = canonical_key(term)
    return (await get_entries(db, [key])).get(key)


async def get_entries(db: AsyncSession, terms: list[str]) -> dict[str, dict]:
    keys = list(dict.fromkeys(canonical_key(term) for term in terms if canonical_key(term)))
    if not keys:
        return {}
    result = await db.execute(
        select(BaseDictionaryEntry).where(
            BaseDictionaryEntry.canonical_key.in_(keys),
            BaseDictionaryEntry.active.is_(True),
        ).order_by(BaseDictionaryEntry.frequency_rank)
    )
    entries_by_key: dict[str, BaseDictionaryEntry] = {}
    for entry in result.scalars().all():
        entries_by_key.setdefault(entry.canonical_key, entry)
    if not entries_by_key:
        return {}
    translations_result = await db.execute(
        select(BaseDictionaryTranslation).where(
            BaseDictionaryTranslation.entry_id.in_(
                entry.id for entry in entries_by_key.values()
            ),
            BaseDictionaryTranslation.locale == "zh-CN",
        )
    )
    translations: dict[tuple, dict] = {
        (item.entry_id, item.sense_key): {
            "definition_zh": item.definition,
            "confidence": item.confidence,
            "generator": item.generator,
        }
        for item in translations_result.scalars().all()
    }
    return {
        key: {
            "id": str(entry.id),
            "canonical_key": entry.canonical_key,
            "lemma": entry.lemma,
            "entry_kind": entry.entry_kind,
            "frequency_zipf": entry.frequency_zipf,
            "frequency_rank": entry.frequency_rank,
            "parts_of_speech": entry.parts_of_speech,
            "pronunciations": entry.pronunciations,
            "forms": entry.forms,
            "senses": [
                {
                    **sense,
                    **translations.get((entry.id, str(sense.get("sense_key"))), {}),
                }
                for sense in entry.senses
            ],
            "relations": entry.relations,
            "examples": entry.examples,
            "source_attribution": entry.source_attribution,
            "build_version": entry.build_version,
        }
        for key, entry in entries_by_key.items()
    }
