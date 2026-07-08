from unittest.mock import AsyncMock, patch

import pytest

from src.config import settings
from src.providers.base import ChatRequest, ChatResponse, EmbedRequest
from src.providers.router import ModelRouter


@pytest.mark.asyncio
async def test_health_check_closes_temporary_clients() -> None:
    router = ModelRouter()
    mock_client = AsyncMock()
    mock_client.health_check = AsyncMock(return_value={"reachable": True})
    mock_client.close = AsyncMock()

    with patch("src.providers.router._create_client", return_value=mock_client):
        result = await router.health_check()

    assert result == {
        "ollama": {"reachable": True},
        "deepseek": {"reachable": True},
        "longcat": {"reachable": True},
    }
    assert mock_client.health_check.await_count == 3
    assert mock_client.close.await_count == 3


@pytest.mark.asyncio
async def test_close_closes_registered_clients() -> None:
    router = ModelRouter()
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()
    router.register("ollama", mock_client)

    await router.close()

    mock_client.close.assert_awaited_once()
    assert router.get("ollama") is None


@pytest.mark.asyncio
async def test_chat_repairs_invalid_structured_json() -> None:
    router = ModelRouter()
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        side_effect=[
            ChatResponse(provider="ollama", model="test", content="not json", structured=None),
            ChatResponse(
                provider="ollama",
                model="test",
                content='{"ok": true}',
                structured={"ok": True},
            ),
        ]
    )
    router.register("ollama", mock_client)

    response = await router.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "return json"}],
            response_schema={"type": "object"},
        )
    )

    assert response.structured == {"ok": True}
    assert response.usage["retry_count"] == 1
    repair_request = mock_client.chat.await_args_list[1].args[0]
    assert repair_request.task_type.endswith(".json_repair")


@pytest.mark.asyncio
async def test_auto_provider_uses_runtime_default_and_strips_ollama_model() -> None:
    router = ModelRouter()
    router.set_default_provider("deepseek")
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=ChatResponse(provider="deepseek", model="deepseek-v4-flash", content="OK")
    )
    router.register("deepseek", mock_client)

    response = await router.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            preferred_model=settings.ollama_chat_model,
        )
    )

    assert response.provider == "deepseek"
    sent_request = mock_client.chat.await_args.args[0]
    assert sent_request.preferred_provider == "deepseek"
    assert sent_request.preferred_model is None


@pytest.mark.asyncio
async def test_embed_stays_on_explicit_ollama_provider() -> None:
    router = ModelRouter()
    router.set_default_provider("deepseek")
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value="embedded")
    router.register("ollama", mock_client)

    result = await router.embed(EmbedRequest(texts=["rag query"]))

    assert result == "embedded"
    mock_client.embed.assert_awaited_once()
