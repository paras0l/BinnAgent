from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools import baidu_translate


def _response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_translate_uses_bearer_key_and_appid(monkeypatch) -> None:
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_app_id", "app-id")
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_api_key", "secret-key")
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_qps", 1000.0)
    client = AsyncMock()
    client.post.return_value = _response(
        {
            "from": "en",
            "to": "zh",
            "trans_result": [
                {"src": "apple", "dst": "苹果"},
                {"src": "A fruit.", "dst": "一种水果。"},
            ],
        }
    )
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(baidu_translate.httpx, "AsyncClient", lambda **_: context)

    result = await baidu_translate.translate_english_to_chinese(["apple", "A fruit."])

    assert result == ["苹果", "一种水果。"]
    request = client.post.await_args
    assert request.kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert request.kwargs["json"]["appid"] == "app-id"
    assert request.kwargs["json"]["model_type"] == "nmt"


@pytest.mark.asyncio
async def test_translate_retries_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_app_id", "app-id")
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_api_key", "secret-key")
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_qps", 1000.0)
    monkeypatch.setattr(baidu_translate.settings, "baidu_translate_max_retries", 1)
    monkeypatch.setattr(baidu_translate.asyncio, "sleep", AsyncMock())
    client = AsyncMock()
    client.post.side_effect = [
        _response({"error_code": "54003", "error_msg": "Access frequency limited"}),
        _response({"trans_result": [{"src": "apple", "dst": "苹果"}]}),
    ]
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(baidu_translate.httpx, "AsyncClient", lambda **_: context)

    assert await baidu_translate.translate_english_to_chinese(["apple"]) == ["苹果"]
    assert client.post.await_count == 2
