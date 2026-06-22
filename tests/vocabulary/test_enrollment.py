import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.vocabulary import VocabularyItem, VocabularyItemSource
from src.tools.free_dictionary import FreeDictionaryEntry
from src.vocabulary import learning


def _one(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_enrollment_enriches_sequence_point_with_free_dictionary(monkeypatch) -> None:
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="textbook.pdf",
        grade="grade-7",
        volume="upper",
        sha256="a" * 64,
        file_size=1,
    )
    source.id = uuid.uuid4()
    node = CurriculumNode(
        source_id=source.id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
    )
    node.id = uuid.uuid4()
    point = KnowledgePoint(
        source_id=source.id,
        curriculum_node_id=node.id,
        canonical_key="vocabulary.sequence.unit-1.1.hello",
        type="vocabulary",
        title="hello",
        summary="Unit 1 单元词表第 1 个词条。",
        source_page="Words and Expressions",
        status="published",
        content={"role": "unit_wordlist", "lemma": "hello", "unit_order": 1},
    )
    point.id = uuid.uuid4()
    learner_id = uuid.uuid4()
    dictionary_entry = FreeDictionaryEntry(
        word="hello",
        phonetic="/həˈləʊ/",
        meanings=[
            {
                "part_of_speech": "noun",
                "definition": "A greeting.",
                "definition_zh": "问候语。",
            }
        ],
        examples=["Hello, Alice!"],
        provider="free_dictionary_api+mymemory",
        phonetic_uk="həˈləʊ",
        phonetic_us="həˈloʊ",
        dictionary_senses=[
            {"part_of_speech": "int.", "meanings_zh": ["你好"]}
        ],
        word_forms={"word_pl": ["hellos"]},
        dictionary_tags=["CET4"],
    )
    lookup = AsyncMock(return_value={"hello": dictionary_entry})
    monkeypatch.setattr(learning, "lookup_free_dictionary_batch", lookup)

    db = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def flush() -> None:
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    db.flush = AsyncMock(side_effect=flush)
    db.execute = AsyncMock(side_effect=[_one(source), _many([point]), _many([]), _many([])])

    result = await learning.enroll_unit_vocabulary(db, learner_id, node)

    item = next(value for value in added if isinstance(value, VocabularyItem))
    item_source = next(value for value in added if isinstance(value, VocabularyItemSource))
    assert result.total == 1
    assert item.phonetic == "/həˈləʊ/"
    assert item.phonetic_uk == "həˈləʊ"
    assert item.phonetic_us == "həˈloʊ"
    assert item.dictionary_senses[0]["meanings_zh"] == ["你好"]
    assert item.word_forms["word_pl"] == ["hellos"]
    assert item.meanings[0]["definition_zh"] == "问候语。"
    assert item.examples == ["Hello, Alice!"]
    assert item.dictionary_provider == dictionary_entry.provider
    assert item.dictionary_enriched_at is not None
    assert item_source.context_snapshot["unit_order"] == 1
    assert item_source.context_snapshot["dictionary_provider"] == dictionary_entry.provider
