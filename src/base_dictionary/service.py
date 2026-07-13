from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base_dictionary.pipeline import canonical_key
from src.models.base_dictionary import BaseDictionaryEntry, BaseDictionaryTranslation


async def get_entry(db: AsyncSession, term: str) -> dict | None:
    key = canonical_key(term)
    result = await db.execute(
        select(BaseDictionaryEntry).where(
            BaseDictionaryEntry.canonical_key == key,
            BaseDictionaryEntry.active.is_(True),
        ).order_by(BaseDictionaryEntry.frequency_rank)
    )
    entry = result.scalars().first()
    if entry is None:
        return None
    translations_result = await db.execute(
        select(BaseDictionaryTranslation).where(
            BaseDictionaryTranslation.entry_id == entry.id,
            BaseDictionaryTranslation.locale == "zh-CN",
        )
    )
    translations = {
        item.sense_key: {
            "definition_zh": item.definition,
            "confidence": item.confidence,
            "generator": item.generator,
        }
        for item in translations_result.scalars().all()
    }
    senses = [
        {**sense, **translations.get(str(sense.get("sense_key")), {})}
        for sense in entry.senses
    ]
    return {
        "id": str(entry.id),
        "canonical_key": entry.canonical_key,
        "lemma": entry.lemma,
        "entry_kind": entry.entry_kind,
        "frequency_zipf": entry.frequency_zipf,
        "frequency_rank": entry.frequency_rank,
        "parts_of_speech": entry.parts_of_speech,
        "pronunciations": entry.pronunciations,
        "forms": entry.forms,
        "senses": senses,
        "relations": entry.relations,
        "examples": entry.examples,
        "source_attribution": entry.source_attribution,
        "build_version": entry.build_version,
    }
