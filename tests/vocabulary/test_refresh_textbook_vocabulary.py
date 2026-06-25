from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import refresh_textbook_vocabulary as refresh


def prepared_entry() -> refresh.PreparedEntry:
    return refresh.PreparedEntry(
        expression="book",
        canonical_key="book",
        point_id="point-1",
        source_id="source-1",
        curriculum_node_id="node-1",
        source_page="Words and Expressions",
        unit_order=1,
        pronunciation=SimpleNamespace(
            phonetic="/old/",
            phonetic_uk="bʊk",
            phonetic_us="bʊk",
            audio_url="https://api.dictionaryapi.dev/media/pronunciations/en/book-uk.mp3",
            audio_uk="https://api.dictionaryapi.dev/media/pronunciations/en/book-uk.mp3",
            audio_us="https://api.dictionaryapi.dev/media/pronunciations/en/book-us.mp3",
            provider="free_dictionary_api",
        ),
        enrichment=SimpleNamespace(
            meanings=[
                {
                    "part_of_speech": "noun",
                    "definition": "a written work",
                    "definition_zh": "书，书籍",
                }
            ],
            dictionary_senses=[
                {"part_of_speech": "n.", "meanings_zh": ["书，书籍"]},
                {"part_of_speech": "v.", "meanings_zh": ["预订，预约"]},
            ],
            word_forms={"word_pl": ["books"], "word_ing": ["booking"]},
            dictionary_tags=["grade-7"],
            examples=[{"en": "I borrowed a book.", "zh": "我借了一本书。"}],
            collocations=["read a book"],
            provider="local_llm:test",
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
    assert item.audio_uk and item.audio_uk.endswith("book-uk.mp3")
    assert item.dictionary_senses[1]["meanings_zh"] == ["预订，预约"]
    assert item.word_forms["word_ing"] == ["booking"]
    assert item.meanings[0]["definition"] == "a written work"
    assert item.meanings[0]["definition_zh"] == "书，书籍"
    assert item.collocations == ["read a book"]
    assert item.dictionary_provider == "free_dictionary_api+local_llm:test"
    assert item.confidence == 0.72
    assert item.review_count == 8


@pytest.mark.asyncio
async def test_overwrite_entries_updates_matching_rows() -> None:
    item = SimpleNamespace(canonical_key="book")
    item.id = "item-1"
    source = SimpleNamespace(
        vocabulary_item_id="item-1",
        source_id="point-1",
        context_snapshot={},
    )
    scalars = MagicMock()
    scalars.all.return_value = [item]
    source_scalars = MagicMock()
    source_scalars.all.return_value = [source]
    item_result = MagicMock()
    item_result.scalars.return_value = scalars
    source_result = MagicMock()
    source_result.scalars.return_value = source_scalars
    db = AsyncMock()
    db.execute.side_effect = [item_result, source_result]

    updated = await refresh.overwrite_entries(db, [prepared_entry()])

    assert updated == 1
    assert item.phonetic_us == "bʊk"
    assert source.context_snapshot["dictionary_provider"] == "free_dictionary_api+local_llm:test"
    assert db.flush.await_count == 2


@pytest.mark.asyncio
async def test_overwrite_entries_upserts_missing_rows_for_learner() -> None:
    learner_id = "learner-1"
    learner_check = MagicMock()
    learner_check.scalar_one_or_none.return_value = learner_id
    empty_scalars = MagicMock()
    empty_scalars.all.return_value = []
    empty_result = MagicMock()
    empty_result.scalars.return_value = empty_scalars
    source_result = MagicMock()
    source_result.scalars.return_value = empty_scalars
    db = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def flush() -> None:
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = "new-item-1"

    db.flush = AsyncMock(side_effect=flush)
    db.execute.side_effect = [learner_check, empty_result, source_result]

    updated = await refresh.overwrite_entries(db, [prepared_entry()], learner_id)

    assert updated == 1
    assert added[0].word == "book"
    assert added[0].dictionary_provider == "free_dictionary_api+local_llm:test"
    assert added[1].source_type == "textbook_unit"
    assert added[1].context_snapshot["dictionary_provider"] == "free_dictionary_api+local_llm:test"
