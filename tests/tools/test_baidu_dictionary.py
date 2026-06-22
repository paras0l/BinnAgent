from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools import baidu_dictionary


def _response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_parse_book_dictionary_payload() -> None:
    entry = baidu_dictionary._parse_entry(
        "book",
        {
            "result": {
                "trans_result": [
                    {
                        "dict": {
                            "word_result": {
                                "simple_means": {
                                    "word_name": "book",
                                    "tags": {"core": ["中考", "高考"]},
                                    "exchange": {
                                        "word_pl": ["books"],
                                        "word_ing": ["booking"],
                                        "word_past": ["booked"],
                                    },
                                    "symbols": [
                                        {
                                            "ph_en": "bʊk",
                                            "ph_am": "bʊk",
                                            "parts": [
                                                {"part": "n.", "means": ["书，书籍"]},
                                                {"part": "v.", "means": ["预订，预约"]},
                                            ],
                                        }
                                    ],
                                },
                                "edict": {
                                    "item": [
                                        {
                                            "pos": "noun",
                                            "tr_group": [
                                                {
                                                    "tr": ["a written or printed work"],
                                                    "example": ["I bought a book."],
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        }
                    }
                ]
            }
        },
    )

    assert entry.phonetic_uk == "bʊk"
    assert entry.phonetic_us == "bʊk"
    assert entry.senses[1]["meanings_zh"] == ["预订，预约"]
    assert entry.word_forms["word_ing"] == ["booking"]
    assert entry.tags == ["中考", "高考"]
    assert entry.english_definitions[0]["definition"] == "a written or printed work"


@pytest.mark.asyncio
async def test_lookup_uses_cached_access_token(monkeypatch) -> None:
    baidu_dictionary._TOKEN = None
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_api_key", "api-key")
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_secret_key", "secret")
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_qps", 1000.0)
    client = AsyncMock()
    client.post.side_effect = [
        _response({"access_token": "token", "expires_in": 3600}),
        _response({"result": {"trans_result": [{"dict": {}}]}}),
    ]
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(baidu_dictionary.httpx, "AsyncClient", lambda **_: context)

    result = await baidu_dictionary.lookup_baidu_dictionary("book")

    assert result.word == "book"
    assert client.post.await_count == 2
    assert client.post.await_args_list[1].kwargs["params"] == {"access_token": "token"}


@pytest.mark.asyncio
async def test_lookup_retries_qps_limit(monkeypatch) -> None:
    baidu_dictionary._TOKEN = ("token", float("inf"))
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_api_key", "api-key")
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_secret_key", "secret")
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_qps", 1000.0)
    monkeypatch.setattr(baidu_dictionary.settings, "baidu_dictionary_max_retries", 2)
    monkeypatch.setattr(baidu_dictionary.asyncio, "sleep", AsyncMock())
    client = AsyncMock()
    client.post.side_effect = [
        _response({"error_code": 18, "error_msg": "Open api qps request limit reached"}),
        _response({"result": {"trans_result": [{"dict": {}}]}}),
    ]
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(baidu_dictionary.httpx, "AsyncClient", lambda **_: context)

    result = await baidu_dictionary.lookup_baidu_dictionary("book")

    assert result.word == "book"
    assert client.post.await_count == 2
