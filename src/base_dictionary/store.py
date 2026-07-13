from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base_dictionary import BaseDictionaryBuild, BaseDictionaryEntry


async def publish_entries(
    db: AsyncSession,
    *,
    version: str,
    entries: list[dict[str, Any]],
    source_manifest: dict[str, Any],
    selection_config: dict[str, Any],
) -> BaseDictionaryBuild:
    """Idempotently publish a staged JSONL build without touching learner-owned rows."""
    result = await db.execute(
        select(BaseDictionaryBuild).where(BaseDictionaryBuild.version == version).with_for_update()
    )
    build = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if build is None:
        build = BaseDictionaryBuild(
            version=version,
            status="loading",
            source_manifest=source_manifest,
            selection_config=selection_config,
            statistics={},
            started_at=now,
        )
        db.add(build)
        await db.flush()
    else:
        build.status = "loading"
        build.source_manifest = source_manifest
        build.selection_config = selection_config

    seen: set[tuple[str, str]] = set()
    requested_keys = [str(payload["canonical_key"]) for payload in entries]
    existing_result = await db.execute(
        select(BaseDictionaryEntry).where(BaseDictionaryEntry.canonical_key.in_(requested_keys))
    )
    existing_by_key = {
        (entry.canonical_key, entry.entry_kind): entry
        for entry in existing_result.scalars().all()
    }
    created = 0
    updated = 0
    for payload in entries:
        key = str(payload["canonical_key"])
        kind = str(payload["entry_kind"])
        seen.add((key, kind))
        entry = existing_by_key.get((key, kind))
        if entry is None:
            entry = BaseDictionaryEntry(canonical_key=key, entry_kind=kind)
            db.add(entry)
            created += 1
        else:
            updated += 1
        entry.lemma = str(payload["lemma"])
        entry.language = "en"
        entry.frequency_zipf = float(payload["frequency_zipf"])
        entry.frequency_rank = int(payload["frequency_rank"])
        entry.parts_of_speech = payload.get("parts_of_speech") or []
        entry.pronunciations = payload.get("pronunciations") or []
        entry.forms = payload.get("forms") or []
        entry.senses = payload.get("senses") or []
        entry.relations = payload.get("relations") or []
        entry.examples = payload.get("examples") or []
        entry.source_attribution = payload.get("source_attribution") or {}
        entry.build_version = version
        entry.active = True

    previous_result = await db.execute(
        select(BaseDictionaryEntry).where(
            BaseDictionaryEntry.active.is_(True),
            BaseDictionaryEntry.build_version != version,
        )
    )
    deactivated = 0
    for entry in previous_result.scalars().all():
        if (entry.canonical_key, entry.entry_kind) not in seen:
            entry.active = False
            deactivated += 1
    build.status = "published"
    build.statistics = {
        "entries": len(entries),
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "words": sum(item.get("entry_kind") == "word" for item in entries),
        "phrases": sum(item.get("entry_kind") != "word" for item in entries),
    }
    build.completed_at = now
    await db.commit()
    await db.refresh(build)
    return build
