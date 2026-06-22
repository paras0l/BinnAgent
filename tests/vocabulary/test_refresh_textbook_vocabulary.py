from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import refresh_textbook_vocabulary as refresh


def prepared_entry() -> refresh.PreparedEntry:
    return refresh.PreparedEntry(
        expression="book",
        canonical_key="book",
        base=SimpleNamespace(
            phonetic="/old/",
            meanings=[
                {
                    "part_of_speech": "noun",
                    "definition": "a written work",
                    "definition_zh": "书，书籍",
                }
            ],
            examples=["I borrowed a book."],
            provider="free_dictionary_api+baidu_translate",
        ),
        rich=SimpleNamespace(
            phonetic_uk="bʊk",
            phonetic_us="bʊk",
            senses=[
                {"part_of_speech": "n.", "meanings_zh": ["书，书籍"]},
                {"part_of_speech": "v.", "meanings_zh": ["预订，预约"]},
            ],
            word_forms={"word_pl": ["books"], "word_ing": ["booking"]},
            tags=["中考"],
            provider="baidu_dictionary_api",
        ),
    )


def test_parse_args_supports_resumable_batch_offset() -> None:
    args = refresh.parse_args(["--limit", "30", "--offset", "60"])

    assert args.limit == 30
    assert args.offset == 60


def test_apply_entry_replaces_dictionary_fields_but_keeps_learning_state() -> None:
    item = SimpleNamespace(
        word="book",
        confidence=0.72,
        review_count=8,
        collocations=["old data"],
    )

    refresh.apply_entry(item, prepared_entry())

    assert item.phonetic_uk == "bʊk"
    assert item.dictionary_senses[1]["meanings_zh"] == ["预订，预约"]
    assert item.word_forms["word_ing"] == ["booking"]
    assert item.meanings[0]["definition"] == "a written work"
    assert item.meanings[0]["definition_zh"] == "书，书籍"
    assert item.collocations == []
    assert item.confidence == 0.72
    assert item.review_count == 8


@pytest.mark.asyncio
async def test_overwrite_entries_updates_matching_rows() -> None:
    item = SimpleNamespace(canonical_key="book")
    scalars = MagicMock()
    scalars.all.return_value = [item]
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute.return_value = result

    updated = await refresh.overwrite_entries(db, [prepared_entry()])

    assert updated == 1
    assert item.phonetic_us == "bʊk"
    db.flush.assert_awaited_once()
