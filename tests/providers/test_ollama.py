from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.providers.base import ChatRequest
from src.providers.ollama import OllamaClient


@pytest.fixture
def ollama_client() -> OllamaClient:
    return OllamaClient(
        base_url="http://test:11434",
        chat_model="test-model:latest",
        utility_model="test-utility:latest",
        embedding_model="test-embedding:latest",
    )


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@pytest.mark.asyncio
async def test_chat_returns_response(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            json_data={
                "model": "test-model:latest",
                "message": {"role": "assistant", "content": "Hello from Ollama"},
                "done_reason": "stop",
                "prompt_eval_count": 15,
                "eval_count": 5,
            },
        )
    )
    ollama_client._client = mock_client

    request = ChatRequest(
        messages=[{"role": "user", "content": "Say hello"}],
        task_type="general",
    )
    response = await ollama_client.chat(request)

    assert response.provider == "ollama"
    assert response.model == "test-model:latest"
    assert response.content == "Hello from Ollama"
    assert response.finish_reason == "stop"
    assert response.usage["input_tokens"] == 15
    assert response.usage["output_tokens"] == 5
    assert response.latency_ms >= 0

    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["model"] == "test-model:latest"
    assert call_kwargs["json"]["messages"] == [{"role": "user", "content": "Say hello"}]
    assert call_kwargs["json"]["stream"] is False


@pytest.mark.asyncio
async def test_chat_with_preferred_model(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            json_data={
                "model": "custom-model",
                "message": {"role": "assistant", "content": "OK"},
                "done_reason": "stop",
            },
        )
    )
    ollama_client._client = mock_client

    request = ChatRequest(
        messages=[{"role": "user", "content": "Hi"}],
        preferred_model="custom-model",
    )
    response = await ollama_client.chat(request)

    assert response.model == "custom-model"
    mock_client.post.assert_awaited_once()
    assert mock_client.post.call_args[1]["json"]["model"] == "custom-model"


@pytest.mark.asyncio
async def test_chat_with_response_schema(ollama_client: OllamaClient) -> None:
    schema = {"type": "object", "properties": {"intent": {"type": "string"}}}
    json_content = '{"intent": "greeting"}'

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            json_data={
                "model": "test-model:latest",
                "message": {"role": "assistant", "content": json_content},
                "done_reason": "stop",
            },
        )
    )
    ollama_client._client = mock_client

    request = ChatRequest(
        messages=[{"role": "user", "content": "Hi"}],
        response_schema=schema,
    )
    response = await ollama_client.chat(request)

    assert response.structured == {"intent": "greeting"}
    assert mock_client.post.call_args[1]["json"]["format"] == schema


@pytest.mark.asyncio
async def test_chat_invalid_json_schema(ollama_client: OllamaClient) -> None:
    schema = {"type": "object"}
    bad_content = "not json at all"

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            json_data={
                "model": "test-model:latest",
                "message": {"role": "assistant", "content": bad_content},
                "done_reason": "stop",
            },
        )
    )
    ollama_client._client = mock_client

    request = ChatRequest(
        messages=[{"role": "user", "content": "Hi"}],
        response_schema=schema,
    )
    response = await ollama_client.chat(request)

    assert response.structured is None
    assert response.content == bad_content


@pytest.mark.asyncio
async def test_chat_http_error(ollama_client: OllamaClient) -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=MagicMock(),
        response=mock_resp,
    )

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)
    ollama_client._client = mock_client

    request = ChatRequest(messages=[{"role": "user", "content": "Hi"}])
    with pytest.raises(httpx.HTTPStatusError):
        await ollama_client.chat(request)


@pytest.mark.asyncio
async def test_health_check_reachable(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            json_data={
                "models": [
                    {"name": "test-model:latest"},
                    {"name": "test-utility:latest"},
                    {"name": "test-embedding:latest"},
                ],
            },
        )
    )
    ollama_client._client = mock_client

    result = await ollama_client.health_check()

    assert result["provider"] == "ollama"
    assert result["reachable"] is True
    assert result["chat_model"]["available"] is True
    assert result["utility_model"]["available"] is True
    assert result["embedding_model"]["available"] is True


@pytest.mark.asyncio
async def test_health_check_unreachable(ollama_client: OllamaClient) -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not found", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    ollama_client._client = mock_client

    result = await ollama_client.health_check()

    assert result["reachable"] is False
    assert result["chat_model"]["available"] is False
    assert result["embedding_model"]["available"] is False
    assert result["utility_model"]["available"] is False


@pytest.mark.asyncio
async def test_health_check_model_not_available(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            json_data={
                "models": [
                    {"name": "some-other-model:latest"},
                ],
            },
        )
    )
    ollama_client._client = mock_client

    result = await ollama_client.health_check()

    assert result["reachable"] is True
    assert result["chat_model"]["available"] is False
    assert result["utility_model"]["available"] is False
    assert result["embedding_model"]["available"] is False


@pytest.mark.asyncio
async def test_health_check_malformed_response_marks_models_unavailable(
    ollama_client: OllamaClient,
) -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.side_effect = ValueError("bad json")

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    ollama_client._client = mock_client

    result = await ollama_client.health_check()

    assert result["reachable"] is True
    assert result["chat_model"]["available"] is False


@pytest.mark.asyncio
async def test_health_check_ignores_malformed_model_entries(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(
        return_value=_mock_response(
            json_data={
                "models": [
                    {"name": "test-model:latest"},
                    {"bad": "entry"},
                    "not-a-dict",
                ],
            },
        )
    )
    ollama_client._client = mock_client

    result = await ollama_client.health_check()

    assert result["reachable"] is True
    assert result["chat_model"]["available"] is True
    assert result["utility_model"]["available"] is False


@pytest.mark.asyncio
async def test_close_cleans_up_client(ollama_client: OllamaClient) -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.aclose = AsyncMock()
    ollama_client._client = mock_client

    await ollama_client.close()

    mock_client.aclose.assert_awaited_once()
    assert ollama_client._client is None


@pytest.mark.asyncio
async def test_close_idempotent(ollama_client: OllamaClient) -> None:
    await ollama_client.close()
    assert ollama_client._client is None
