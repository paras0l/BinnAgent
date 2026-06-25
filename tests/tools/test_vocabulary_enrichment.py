from unittest.mock import AsyncMock

import pytest

from src.providers.base import ChatResponse
from src.tools import vocabulary_enrichment
from src.tools.free_dictionary import FreeDictionaryEntry


def test_build_prompt_keeps_pronunciation_source_on_free_dictionary() -> None:
    entry = FreeDictionaryEntry(
        word="book",
        phonetic="/bʊk/",
        phonetic_uk="/bʊk/",
        phonetic_us="/bʊk/",
        audio_url="https://api.dictionaryapi.dev/media/pronunciations/en/book-uk.mp3",
        meanings=[{"part_of_speech": "noun", "definition": "A written work.", "definition_zh": ""}],
        examples=["I read a book."],
        provider="free_dictionary_api",
    )

    prompt = vocabulary_enrichment.build_vocabulary_enrichment_prompt("book", entry)

    assert "发音音标和音频只来自 Free Dictionary API" in prompt
    assert "你只补全语义、中文释义、例句、词形、标签和搭配" in prompt
    assert "book" in prompt


def test_build_prompt_treats_single_uppercase_letter_as_letter() -> None:
    entry = FreeDictionaryEntry(
        word="p",
        phonetic="/piː/",
        meanings=[{"part_of_speech": "noun", "definition": "pence.", "definition_zh": ""}],
        examples=["It costs 50p."],
        provider="free_dictionary_api",
    )

    prompt = vocabulary_enrichment.build_vocabulary_enrichment_prompt("P", entry)

    assert '"entry_kind": "single_letter"' in prompt
    assert '"meanings": []' in prompt
    assert "忽略便士、页码等普通词典义项" in prompt
    assert "不要说 first/last" in prompt


def test_parse_local_vocabulary_payload_normalizes_shapes() -> None:
    parsed = vocabulary_enrichment.parse_local_vocabulary_payload(
        {
            "meanings": [
                {
                    "part_of_speech": "noun",
                    "definition": "A written work.",
                    "definition_zh": "书。",
                }
            ],
            "dictionary_senses": [
                {"part_of_speech": "n.", "meanings_zh": ["书", "", 3]},
            ],
            "word_forms": {"word_pl": ["books", ""]},
            "dictionary_tags": ["grade-7", ""],
            "examples": [{"en": "I read a book.", "zh": "我读一本书。"}],
            "collocations": ["read a book"],
        }
    )

    assert parsed.meanings[0]["definition_zh"] == "书。"
    assert parsed.dictionary_senses == [{"part_of_speech": "n.", "meanings_zh": ["书"]}]
    assert parsed.word_forms == {"word_pl": ["books"]}
    assert parsed.dictionary_tags == ["grade-7"]
    assert parsed.collocations == ["read a book"]


def test_single_letter_sanitizer_removes_order_hallucinations() -> None:
    entry = vocabulary_enrichment.LocalVocabularyEntry(
        meanings=[
            {
                "part_of_speech": "noun",
                "definition": "pence.",
                "definition_zh": "便士。",
            }
        ],
        dictionary_senses=[{"part_of_speech": "n.", "meanings_zh": ["便士"]}],
        examples=[
            {"en": "P is the first letter of the alphabet.", "zh": "P 是第一个字母。"},
            {"en": "This is the letter P.", "zh": "这是字母 P。"},
        ],
        provider="ollama:test",
    )

    sanitized = vocabulary_enrichment._sanitize_single_letter_entry("P", entry)

    assert sanitized.dictionary_senses == [
        {"part_of_speech": "letter", "meanings_zh": ["字母 P"]}
    ]
    assert sanitized.examples == [{"en": "This is the letter P.", "zh": "这是字母 P。"}]


@pytest.mark.asyncio
async def test_enrich_vocabulary_with_local_model_uses_router_schema(monkeypatch) -> None:
    entry = FreeDictionaryEntry(
        word="book",
        phonetic="/bʊk/",
        meanings=[],
        examples=[],
        provider="free_dictionary_api",
    )
    chat = AsyncMock(
        return_value=ChatResponse(
            provider="ollama",
            model="gemma4:e2b",
            content="{}",
            structured={
                "meanings": [
                    {
                        "part_of_speech": "noun",
                        "definition": "A written work.",
                        "definition_zh": "书。",
                    }
                ],
                "dictionary_senses": [{"part_of_speech": "n.", "meanings_zh": ["书"]}],
                "word_forms": {"word_pl": ["books"]},
                "dictionary_tags": ["grade-7"],
                "examples": [{"en": "This is a book.", "zh": "这是一本书。"}],
                "collocations": ["read a book"],
            },
        )
    )
    monkeypatch.setattr(vocabulary_enrichment.router, "chat", chat)

    result = await vocabulary_enrichment.enrich_vocabulary_with_local_model("book", entry)

    request = chat.await_args.args[0]
    assert request.task_type == "vocabulary_local_enrichment"
    assert request.response_schema is vocabulary_enrichment.LOCAL_VOCABULARY_SCHEMA
    assert request.local_only is True
    assert result.provider == "ollama:gemma4:e2b"
    assert result.dictionary_senses[0]["meanings_zh"] == ["书"]
