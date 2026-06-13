from typing import Any, AsyncIterator

from src.providers.base import ChatRequest, ChatResponse, ChatStreamChunk
from src.providers.ollama import OllamaClient


class ModelRouter:
    def __init__(self) -> None:
        self._clients: dict[str, OllamaClient] = {}

    def register(self, name: str, client: OllamaClient) -> None:
        self._clients[name] = client

    def get(self, name: str) -> OllamaClient | None:
        return self._clients.get(name)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = self._get_or_create_client(request.preferred_provider)
        return await client.chat(request)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        client = self._get_or_create_client(request.preferred_provider)
        async for chunk in client.stream_chat(request):
            yield chunk

    def _get_or_create_client(self, provider: str) -> OllamaClient:
        client = self._clients.get(provider)

        if client is None:
            client = OllamaClient()
            self._clients[provider] = client

        return client

    async def health_check(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, client in self._clients.items():
            results[name] = await client.health_check()
        if not results:
            ollama = OllamaClient()
            try:
                results["ollama"] = await ollama.health_check()
            finally:
                await ollama.close()
        return results

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


router = ModelRouter()
