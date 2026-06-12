from unittest.mock import AsyncMock

import httpx
import pytest

from src.api import deps
from src.main import app
from src.providers.base import ChatResponse as ModelChatResponse
from src.providers.router import ModelRouter


@pytest.fixture
def mock_model_router():
    router = AsyncMock(spec=ModelRouter)
    app.dependency_overrides[deps.get_model_router] = lambda: router
    yield router
    app.dependency_overrides.clear()


class TestChatSend:
    @pytest.mark.asyncio
    async def test_chat_send_returns_reply_and_response_alias(self, client, mock_model_router):
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(
                provider="ollama",
                model="gemma4:e2b",
                content="你好，我可以帮你练习阅读。",
            )
        )

        response = await client.post("/api/chat/send", json={"message": "我想练习阅读"})

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "你好，我可以帮你练习阅读。"
        assert data["response"] == "你好，我可以帮你练习阅读。"
        assert data["skill_focus"] is None
        mock_model_router.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_send_uses_skill_focus_in_system_message(self, client, mock_model_router):
        mock_model_router.chat = AsyncMock(
            return_value=ModelChatResponse(provider="ollama", model="gemma4:e2b", content="OK")
        )

        response = await client.post(
            "/api/chat/send",
            json={"message": "帮我练一下", "skill_focus": "writing"},
        )

        assert response.status_code == 200
        request = mock_model_router.chat.await_args.args[0]
        assert request.task_type == "learning_chat"
        assert request.temperature == 0.7
        assert request.max_tokens == 1024
        assert "当前重点练习: writing" in request.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_chat_send_blank_message_returns_422(self, client):
        response = await client.post("/api/chat/send", json={"message": "   "})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_send_model_http_error_returns_stable_503(self, client, mock_model_router):
        mock_model_router.chat = AsyncMock(side_effect=httpx.ConnectError("secret host detail"))

        response = await client.post("/api/chat/send", json={"message": "hello"})

        assert response.status_code == 503
        assert response.json()["detail"] == "Ollama service unavailable"
