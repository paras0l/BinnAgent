from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base_dictionary import BaseDictionaryEntry, BaseDictionaryTranslation
from src.prompts import PromptExecutionContext, PromptExecutor


async def translate_entry_batch(
    db: AsyncSession,
    *,
    entries: list[BaseDictionaryEntry],
    executor: PromptExecutor,
) -> int:
    requested = [
        {
            "canonical_key": entry.canonical_key,
            "lemma": entry.lemma,
            "senses": [
                {
                    "sense_key": sense["sense_key"],
                    "part_of_speech": sense.get("part_of_speech", "unknown"),
                    "definition_en": sense["definition_en"],
                }
                for sense in entry.senses[:3]
            ],
        }
        for entry in entries
    ]
    result = await executor.execute(
        prompt_id="base_dictionary.translate_zh",
        variables={"entries": requested},
        context=PromptExecutionContext(
            source_module="base_dictionary.translation",
            task_id="base_dictionary_translate_zh",
            target_type="base_dictionary_batch",
            metadata={"entry_count": len(entries)},
        ),
        request_overrides={"task_type": "base_dictionary_translate_zh"},
    )
    if result.decision != "accepted" or result.validated_output is None:
        raise RuntimeError("Chinese dictionary translation was not accepted")
    entries_by_key = {entry.canonical_key: entry for entry in entries}
    written = 0
    for translated_entry in result.validated_output.get("entries", []):
        entry = entries_by_key.get(str(translated_entry.get("canonical_key", "")))
        if entry is None:
            continue
        senses_by_key = {
            str(sense["sense_key"]): sense
            for sense in entry.senses
            if sense.get("sense_key") and sense.get("definition_en")
        }
        for translated_sense in translated_entry.get("senses", []):
            sense_key = str(translated_sense.get("sense_key", ""))
            source_sense = senses_by_key.get(sense_key)
            definition = str(translated_sense.get("definition_zh", "")).strip()
            if source_sense is None or not definition:
                continue
            source_hash = hashlib.sha256(
                str(source_sense["definition_en"]).encode("utf-8")
            ).hexdigest()
            existing_result = await db.execute(
                select(BaseDictionaryTranslation).where(
                    BaseDictionaryTranslation.entry_id == entry.id,
                    BaseDictionaryTranslation.sense_key == sense_key,
                    BaseDictionaryTranslation.locale == "zh-CN",
                )
            )
            translation = existing_result.scalar_one_or_none()
            if translation is None:
                translation = BaseDictionaryTranslation(
                    entry_id=entry.id,
                    sense_key=sense_key,
                    locale="zh-CN",
                )
                db.add(translation)
            translation.definition = definition
            translation.generator = result.model or result.provider or "unknown"
            translation.prompt_version = result.prompt_version
            translation.source_definition_hash = source_hash
            translation.confidence = float(translated_sense.get("confidence", 0.0))
            translation.generated_at = datetime.now(timezone.utc)
            written += 1
    await db.commit()
    return written


async def untranslated_entries(
    db: AsyncSession, *, limit: int, offset: int = 0
) -> list[BaseDictionaryEntry]:
    result = await db.execute(
        select(BaseDictionaryEntry)
        .outerjoin(
            BaseDictionaryTranslation,
            (BaseDictionaryTranslation.entry_id == BaseDictionaryEntry.id)
            & (BaseDictionaryTranslation.locale == "zh-CN"),
        )
        .where(BaseDictionaryEntry.active.is_(True))
        .group_by(BaseDictionaryEntry.id)
        .having(
            func.count(BaseDictionaryTranslation.id)
            < func.jsonb_array_length(BaseDictionaryEntry.senses)
        )
        .order_by(BaseDictionaryEntry.frequency_rank)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())
