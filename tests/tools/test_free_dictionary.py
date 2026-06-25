from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools import free_dictionary


def _response(status: int, payload: object) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_lookup_uses_free_dictionary_pronunciation_audio_and_definitions(
    monkeypatch,
) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get = AsyncMock(
        return_value=_response(
            200,
            [
                {
                    "word": "hello",
                    "phonetic": "/həˈləʊ/",
                    "phonetics": [
                        {
                            "text": "/həˈləʊ/",
                            "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-uk.mp3",
                        },
                        {
                            "text": "/həˈloʊ/",
                            "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-us.mp3",
                        },
                    ],
                    "meanings": [
                        {
                            "partOfSpeech": "noun",
                            "definitions": [
                                {
                                    "definition": "A greeting.",
                                    "example": "Hello, Alice!",
                                }
                            ],
                        }
                    ],
                }
            ],
        )
    )
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(free_dictionary.httpx, "AsyncClient", lambda **_: context)

    result = await free_dictionary.lookup_free_dictionary("Hello")

    assert result.phonetic == "/həˈləʊ/"
    assert result.phonetic_uk == "/həˈləʊ/"
    assert result.phonetic_us == "/həˈloʊ/"
    assert result.audio_uk and result.audio_uk.endswith("hello-uk.mp3")
    assert result.audio_us and result.audio_us.endswith("hello-us.mp3")
    assert result.meanings == [
        {
            "part_of_speech": "noun",
            "definition": "A greeting.",
            "definition_zh": "",
        }
    ]
    assert result.examples == ["Hello, Alice!"]
    assert result.provider == "free_dictionary_api"


@pytest.mark.asyncio
async def test_lookup_returns_empty_api_result_for_unknown_expression(monkeypatch) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response(404, {"title": "No Definitions Found"}))
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(free_dictionary.httpx, "AsyncClient", lambda **_: context)

    result = await free_dictionary.lookup_free_dictionary("not-a-real-entry")

    assert result.meanings == []
    assert result.provider == "free_dictionary_not_found"
