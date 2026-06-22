from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools import free_dictionary


def _response(status: int, payload: object) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_lookup_uses_free_dictionary_and_translates_definitions(monkeypatch) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get = AsyncMock(
        return_value=_response(
            200,
            [
                {
                    "word": "hello",
                    "phonetics": [{"text": "/həˈləʊ/"}],
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
    monkeypatch.setattr(
        free_dictionary,
        "translate_english_to_chinese",
        AsyncMock(return_value=["问候语。"]),
    )

    result = await free_dictionary.lookup_free_dictionary("Hello")

    assert result.phonetic == "/həˈləʊ/"
    assert result.meanings == [
        {
            "part_of_speech": "noun",
            "definition": "A greeting.",
            "definition_zh": "问候语。",
        }
    ]
    assert result.examples == ["Hello, Alice!"]
    assert result.provider == "free_dictionary_api+baidu_translate"


@pytest.mark.asyncio
async def test_lookup_returns_empty_api_result_for_unknown_expression(monkeypatch) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response(404, {"title": "No Definitions Found"}))
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(free_dictionary.httpx, "AsyncClient", lambda **_: context)
    monkeypatch.setattr(
        free_dictionary,
        "translate_english_to_chinese",
        AsyncMock(side_effect=free_dictionary.BaiduTranslateError("unavailable")),
    )

    result = await free_dictionary.lookup_free_dictionary("not-a-real-entry")

    assert result.meanings == []
    assert result.provider == "free_dictionary_not_found"


@pytest.mark.asyncio
async def test_lookup_uses_baidu_fallback_for_unknown_expression(monkeypatch) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get.return_value = _response(404, {"title": "No Definitions Found"})
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(free_dictionary.httpx, "AsyncClient", lambda **_: context)
    monkeypatch.setattr(
        free_dictionary,
        "translate_english_to_chinese",
        AsyncMock(return_value=["电话号码"]),
    )

    result = await free_dictionary.lookup_free_dictionary("telephone number")

    assert result.meanings[0]["definition_zh"] == "电话号码"
    assert result.provider == "baidu_translate_fallback"


@pytest.mark.asyncio
async def test_lookup_marks_baidu_failure_for_retry(monkeypatch) -> None:
    free_dictionary._CACHE.clear()
    client = AsyncMock()
    client.get.return_value = _response(
        200,
        [
            {
                "word": "hello",
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [{"definition": "A greeting."}],
                    }
                ],
            }
        ],
    )
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(free_dictionary.httpx, "AsyncClient", lambda **_: context)
    monkeypatch.setattr(
        free_dictionary,
        "translate_english_to_chinese",
        AsyncMock(side_effect=free_dictionary.BaiduTranslateError("not enabled")),
    )

    result = await free_dictionary.lookup_free_dictionary("hello")

    assert result.meanings[0]["definition_zh"] == ""
    assert result.provider == "free_dictionary_api+baidu_translate_error"
