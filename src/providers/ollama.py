import json
import time
from typing import Any

import httpx

from src.config import settings
from src.providers.base import ChatRequest, ChatResponse, ModelClient


class OllamaClient(ModelClient):
    def __init__(
        self,
        base_url: str | None = None,
        chat_model: str | None = None,
        utility_model: str | None = None,
        embedding_model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.chat_model = chat_model or settings.ollama_chat_model
        self.utility_model = utility_model or settings.ollama_utility_model
        self.embedding_model = embedding_model or settings.ollama_embedding_model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": request.preferred_model or self.chat_model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        if request.response_schema:
            payload["format"] = request.response_schema

        start = time.monotonic()
        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        elapsed = int((time.monotonic() - start) * 1000)

        data = response.json()
        content = data.get("message", {}).get("content", "")
        finish_reason = data.get("done_reason", "stop")

        usage: dict[str, Any] = {}
        if "prompt_eval_count" in data:
            usage["input_tokens"] = data["prompt_eval_count"]
        if "eval_count" in data:
            usage["output_tokens"] = data["eval_count"]

        structured: dict[str, Any] | None = None
        if request.response_schema:
            try:
                structured = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                structured = None

        return ChatResponse(
            provider="ollama",
            model=payload["model"],
            content=content,
            structured=structured,
            latency_ms=elapsed,
            usage=usage,
            finish_reason=finish_reason,
        )

    async def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "provider": "ollama",
            "reachable": False,
            "chat_model": {"name": self.chat_model, "available": False},
            "utility_model": {"name": self.utility_model, "available": False},
            "embedding_model": {"name": self.embedding_model, "available": False},
        }

        try:
            resp = await self.client.get("/api/tags")
            resp.raise_for_status()
            result["reachable"] = True

            models_data = resp.json()
            models = models_data.get("models", []) if isinstance(models_data, dict) else []
            available_models = {
                m["name"] for m in models if isinstance(m, dict) and isinstance(m.get("name"), str)
            }

            result["chat_model"]["available"] = self.chat_model in available_models
            result["utility_model"]["available"] = self.utility_model in available_models
            result["embedding_model"]["available"] = self.embedding_model in available_models
        except (httpx.HTTPError, ValueError, TypeError):
            pass

        return result

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
