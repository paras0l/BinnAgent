import json
from typing import Any, AsyncIterator

from src.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbedRequest,
    EmbedResponse,
)
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
        response = await client.chat(request)
        if request.response_schema and response.structured is None:
            repair_request = ChatRequest(
                messages=[
                    *request.messages,
                    {
                        "role": "assistant",
                        "content": response.content,
                    },
                    {
                        "role": "user",
                        "content": (
                            "请修复上一条回复，使其成为严格合法的 JSON。"
                            "只输出 JSON，不要添加解释、Markdown 或代码块。"
                        ),
                    },
                ],
                task_type=f"{request.task_type}.json_repair",
                temperature=0,
                max_tokens=request.max_tokens,
                response_schema=request.response_schema,
                preferred_provider=request.preferred_provider,
                preferred_model=request.preferred_model,
                local_only=request.local_only,
            )
            repaired = await client.chat(repair_request)
            if repaired.structured is not None:
                repaired.usage = {
                    **repaired.usage,
                    "retry_count": 1,
                    "repair_reason": "invalid_json",
                }
                return repaired
            try:
                repaired.structured = json.loads(repaired.content)
                repaired.usage = {
                    **repaired.usage,
                    "retry_count": 1,
                    "repair_reason": "invalid_json",
                }
                return repaired
            except (json.JSONDecodeError, TypeError):
                response.usage = {
                    **response.usage,
                    "retry_count": 1,
                    "repair_failed": True,
                }
        return response

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        client = self._get_or_create_client(request.preferred_provider)
        async for chunk in client.stream_chat(request):
            yield chunk

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        client = self._get_or_create_client(request.preferred_provider)
        return await client.embed(request)

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
