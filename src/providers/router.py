from typing import Any

from src.providers.base import ChatRequest, ChatResponse
from src.providers.ollama import OllamaClient


class ModelRouter:
    def __init__(self) -> None:
        self._clients: dict[str, OllamaClient] = {}

    def register(self, name: str, client: OllamaClient) -> None:
        self._clients[name] = client

    def get(self, name: str) -> OllamaClient | None:
        return self._clients.get(name)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        provider = request.preferred_provider
        client = self._clients.get(provider)

        if client is None:
            client = OllamaClient()
            self._clients[provider] = client

        return await client.chat(request)

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
