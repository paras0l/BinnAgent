import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.base_dictionary.service import get_entries, get_entry
from src.models.base_dictionary import BaseDictionaryEntry, BaseDictionaryTranslation


def _many(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _entry(key: str, rank: int) -> BaseDictionaryEntry:
    entry = BaseDictionaryEntry(
        id=uuid.uuid4(),
        canonical_key=key,
        lemma=key,
        language="en",
        entry_kind="word",
        frequency_zipf=5.0,
        frequency_rank=rank,
        parts_of_speech=["noun"],
        pronunciations=[],
        forms=[],
        senses=[
            {
                "sense_key": f"{key}-n-1",
                "part_of_speech": "noun",
                "definition_en": f"definition of {key}",
            }
        ],
        relations=[],
        examples=[],
        source_attribution={},
        build_version="2026-07-12.1",
        active=True,
    )
    return entry


@pytest.mark.asyncio
async def test_get_entries_batches_entries_and_chinese_translations() -> None:
    library = _entry("library", 1)
    school = _entry("school", 2)
    translation = BaseDictionaryTranslation(
        entry_id=library.id,
        sense_key="library-n-1",
        locale="zh-CN",
        definition="图书馆",
        generator="test",
        prompt_version="v1",
        source_definition_hash="a" * 64,
        confidence=0.99,
        generated_at=library.created_at,
    )
    db = AsyncMock()
    db.execute.side_effect = [_many([library, school]), _many([translation])]

    payload = await get_entries(db, [" Library ", "school", "library"])

    assert set(payload) == {"library", "school"}
    assert payload["library"]["senses"][0]["definition_zh"] == "图书馆"
    assert "definition_zh" not in payload["school"]["senses"][0]
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_entry_returns_none_when_term_is_missing() -> None:
    db = AsyncMock()
    db.execute.return_value = _many([])

    assert await get_entry(db, "not-in-dictionary") is None
    assert db.execute.await_count == 1
