import json
from typing import Any, AsyncIterator

from jsonschema import Draft202012Validator

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
        schema_error = _structured_schema_error(response, request.response_schema)
        if request.response_schema and schema_error is not None:
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
                            "请修复上一条回复，使其通过目标 JSON Schema 校验。"
                            f"当前校验错误：{schema_error}。"
                            "保留原有语义，只修正结构、字段和类型；"
                            "必填字段不得省略，只输出 JSON。"
                        ),
                    },
                ],
                task_type=f"{routed_request.task_type}.json_repair",
                temperature=0,
                max_tokens=routed_request.max_tokens,
                response_schema=routed_request.response_schema,
                metadata=routed_request.metadata,
                preferred_provider=provider,
                preferred_model=routed_request.preferred_model,
                local_only=routed_request.local_only,
            )
            repaired = await client.chat(repair_request)
            repaired_schema_error = _structured_schema_error(repaired, request.response_schema)
            if repaired_schema_error is None:
                repaired.usage = {
                    **repaired.usage,
                    "retry_count": 1,
                    "repair_reason": schema_error,
                }
                return repaired
            repaired.usage = {
                **repaired.usage,
                "retry_count": 1,
                "repair_reason": schema_error,
                "repair_failed": True,
                "repair_error": repaired_schema_error,
            }
            return repaired
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


def _structured_schema_error(
    response: ChatResponse,
    response_schema: dict[str, Any] | None,
) -> str | None:
    if response_schema is None:
        return None
    payload = response.structured
    if not isinstance(payload, dict):
        try:
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return "回复不是合法的 JSON 对象"
        if not isinstance(parsed, dict):
            return f"顶层必须是 JSON 对象，实际为 {type(parsed).__name__}"
        payload = parsed
        response.structured = parsed

    errors = sorted(
        Draft202012Validator(response_schema).iter_errors(payload),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if not errors:
        return None
    error = errors[0]
    path = ".".join(str(part) for part in error.absolute_path) or "$"
    return f"{path}: {error.message}"


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
