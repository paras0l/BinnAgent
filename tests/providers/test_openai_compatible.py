from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.providers.base import ChatRequest
from src.providers.openai_compatible import OpenAICompatibleClient


def _mock_response(json_data: dict) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_chat_uses_openai_compatible_payload() -> None:
    client = OpenAICompatibleClient(
        provider="deepseek",
        base_url="https://api.example.test",
        api_key="secret",
        chat_model="chat-model",
        supports_response_format=True,
    )
    mock_http = MagicMock(spec=httpx.AsyncClient)
    mock_http.post = AsyncMock(
        return_value=_mock_response(
            {
                "model": "chat-model",
                "choices": [
                    {
                        "message": {"content": '{"ok": true}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            }
        )
    )
    client._client = mock_http

    response = await client.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "return json"}],
            response_schema={"type": "object"},
        )
    )

    assert response.provider == "deepseek"
    assert response.model == "chat-model"
    assert response.structured == {"ok": True}
    assert response.usage["input_tokens"] == 10
    assert mock_http.post.call_args.args == ("/chat/completions",)
    payload = mock_http.post.call_args.kwargs["json"]
    assert payload["model"] == "chat-model"
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_health_check_without_api_key_is_not_reachable() -> None:
    client = OpenAICompatibleClient(
        provider="longcat",
        base_url="https://api.example.test",
        api_key=None,
        chat_model="LongCat-2.0",
    )

    result = await client.health_check()

    assert result["provider"] == "longcat"
    assert result["api_key_configured"] is False
    assert result["reachable"] is False


@pytest.mark.asyncio
async def test_chat_injects_compact_schema_when_provider_lacks_response_format() -> None:
    client = OpenAICompatibleClient(
        provider="longcat",
        base_url="https://api.example.test",
        api_key="secret",
        chat_model="LongCat-2.0",
        supports_response_format=False,
    )
    mock_http = MagicMock(spec=httpx.AsyncClient)
    mock_http.post = AsyncMock(
        return_value=_mock_response(
            {
                "model": "LongCat-2.0",
                "choices": [
                    {
                        "message": {"content": '{"confidence":0.9,"feedback":"ok"}'},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
    )
    client._client = mock_http
    schema = {
        "type": "object",
        "required": ["confidence", "feedback"],
        "properties": {
            "confidence": {"type": "number"},
            "feedback": {"type": "string"},
        },
    }

    await client.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "return json"}],
            response_schema=schema,
            metadata={"thinking": "disabled"},
        )
    )

    payload = mock_http.post.call_args.kwargs["json"]
    assert "response_format" not in payload
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["messages"][-1]["role"] == "user"
    assert '"required":["confidence","feedback"]' in payload["messages"][-1]["content"]
    assert "必填字段不得省略" in payload["messages"][-1]["content"]
