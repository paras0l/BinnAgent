from unittest.mock import AsyncMock, patch

import pytest

from src.providers.router import ModelRouter


@pytest.mark.asyncio
async def test_health_check_closes_temporary_ollama_client() -> None:
    router = ModelRouter()
    mock_client = AsyncMock()
    mock_client.health_check = AsyncMock(return_value={"reachable": True})
    mock_client.close = AsyncMock()

    with patch("src.providers.router.OllamaClient", return_value=mock_client):
        result = await router.health_check()

    assert result == {"ollama": {"reachable": True}}
    mock_client.health_check.assert_awaited_once()
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_closes_registered_clients() -> None:
    router = ModelRouter()
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()
    router.register("ollama", mock_client)

    await router.close()

    mock_client.close.assert_awaited_once()
    assert router.get("ollama") is None
