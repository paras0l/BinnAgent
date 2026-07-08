import json
from typing import Any, AsyncIterator

from src.config import settings
from src.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbedRequest,
    EmbedResponse,
    ModelClient,
)
from src.providers.ollama import OllamaClient
from src.providers.openai_compatible import OpenAICompatibleClient


KNOWN_PROVIDERS = ("ollama", "deepseek", "longcat")


class ModelRouter:
    def __init__(self) -> None:
        self._clients: dict[str, ModelClient] = {}
        self._default_provider = _normalized_provider(settings.model_provider)

    @property
    def default_provider(self) -> str:
        return self._default_provider

    def set_default_provider(self, provider: str) -> None:
        self._default_provider = _normalized_provider(provider)

    def register(self, name: str, client: ModelClient) -> None:
        self._clients[_normalized_provider(name)] = client

    def get(self, name: str) -> ModelClient | None:
        return self._clients.get(_normalized_provider(name))

    async def chat(self, request: ChatRequest) -> ChatResponse:
        provider = self._resolve_provider(request.preferred_provider)
        routed_request = self._routed_chat_request(request, provider)
        client = self._get_or_create_client(provider)
        response = await client.chat(routed_request)
        if request.response_schema and response.structured is None:
            repair_request = ChatRequest(
                messages=[
                    *routed_request.messages,
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
                task_type=f"{routed_request.task_type}.json_repair",
                temperature=0,
                max_tokens=routed_request.max_tokens,
                response_schema=routed_request.response_schema,
                preferred_provider=provider,
                preferred_model=routed_request.preferred_model,
                local_only=routed_request.local_only,
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
        provider = self._resolve_provider(request.preferred_provider)
        routed_request = self._routed_chat_request(request, provider)
        client = self._get_or_create_client(provider)
        async for chunk in client.stream_chat(routed_request):
            yield chunk

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        client = self._get_or_create_client(_normalized_provider(request.preferred_provider))
        return await client.embed(request)

    def _resolve_provider(self, provider: str | None) -> str:
        if not provider or provider == "auto":
            return self._default_provider
        return _normalized_provider(provider)

    def _routed_chat_request(self, request: ChatRequest, provider: str) -> ChatRequest:
        preferred_model = request.preferred_model
        if provider != "ollama" and preferred_model in {
            settings.ollama_chat_model,
            settings.ollama_utility_model,
        }:
            preferred_model = None
        return ChatRequest(
            messages=request.messages,
            task_type=request.task_type,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_schema=request.response_schema,
            metadata=request.metadata,
            preferred_provider=provider,
            preferred_model=preferred_model,
            local_only=request.local_only,
        )

    def _get_or_create_client(self, provider: str) -> ModelClient:
        provider = _normalized_provider(provider)
        client = self._clients.get(provider)

        if client is None:
            client = _create_client(provider)
            self._clients[provider] = client

        return client

    async def health_check(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name in KNOWN_PROVIDERS:
            client = self._clients.get(name) or _create_client(name)
            try:
                results[name] = await client.health_check()
            finally:
                if name not in self._clients:
                    await client.close()
        return results

    async def provider_status(self) -> dict[str, Any]:
        health = await self.health_check()
        return {
            "active_provider": self._default_provider,
            "configured_provider": _normalized_provider(settings.model_provider),
            "rag_provider": "ollama",
            "providers": [_provider_summary(name, health.get(name, {})) for name in KNOWN_PROVIDERS],
        }

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


def _normalized_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in KNOWN_PROVIDERS:
        raise ValueError(f"Unsupported model provider: {provider}")
    return normalized


def _create_client(provider: str) -> ModelClient:
    if provider == "ollama":
        return OllamaClient()
    if provider == "deepseek":
        return OpenAICompatibleClient(
            provider="deepseek",
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            chat_model=settings.deepseek_chat_model,
            utility_model=settings.deepseek_utility_model,
            chat_path="/chat/completions",
            models_path="/models",
            supports_response_format=True,
        )
    if provider == "longcat":
        return OpenAICompatibleClient(
            provider="longcat",
            base_url=settings.longcat_base_url,
            api_key=settings.longcat_api_key,
            chat_model=settings.longcat_chat_model,
            utility_model=settings.longcat_utility_model,
            chat_path="/v1/chat/completions",
            models_path="/v1/models",
            supports_response_format=False,
        )
    raise ValueError(f"Unsupported model provider: {provider}")


def _provider_summary(name: str, health: dict[str, Any]) -> dict[str, Any]:
    if name == "ollama":
        return {
            "id": name,
            "label": "Ollama",
            "base_url": settings.ollama_base_url,
            "chat_model": settings.ollama_chat_model,
            "utility_model": settings.ollama_utility_model,
            "embedding_model": settings.ollama_embedding_model,
            "api_key_configured": True,
            "supports_streaming": True,
            "supports_embeddings": True,
            "health": health,
        }
    if name == "deepseek":
        return {
            "id": name,
            "label": "DeepSeek",
            "base_url": settings.deepseek_base_url,
            "chat_model": settings.deepseek_chat_model,
            "utility_model": settings.deepseek_utility_model,
            "embedding_model": None,
            "api_key_configured": bool(settings.deepseek_api_key),
            "supports_streaming": True,
            "supports_embeddings": False,
            "health": health,
        }
    return {
        "id": name,
        "label": "LongCat",
        "base_url": settings.longcat_base_url,
        "chat_model": settings.longcat_chat_model,
        "utility_model": settings.longcat_utility_model,
        "embedding_model": None,
        "api_key_configured": bool(settings.longcat_api_key),
        "supports_streaming": True,
        "supports_embeddings": False,
        "health": health,
    }


router = ModelRouter()
