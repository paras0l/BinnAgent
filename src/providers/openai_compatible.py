import json
import time
from typing import Any, AsyncIterator

import httpx

from src.observability import observe
from src.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbedRequest,
    EmbedResponse,
    ModelClient,
)


class OpenAICompatibleClient(ModelClient):
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str | None,
        chat_model: str,
        utility_model: str | None = None,
        chat_path: str = "/chat/completions",
        models_path: str = "/models",
        supports_response_format: bool = False,
        timeout: float = 90.0,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.chat_model = chat_model
        self.utility_model = utility_model or chat_model
        self.chat_path = chat_path
        self.models_path = models_path
        self.supports_response_format = supports_response_format
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=self._headers(),
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._chat_payload(request, stream=False)
        with observe(
            f"{self.provider}-chat",
            as_type="generation",
            input={"task_type": request.task_type, "messages": request.messages},
            metadata={"model": payload["model"], "provider": self.provider},
        ) as generation:
            start = time.monotonic()
            response = await self.client.post(self.chat_path, json=payload)
            response.raise_for_status()
            elapsed = int((time.monotonic() - start) * 1000)

            data = response.json()
            choice = _first_choice(data)
            content = _message_content(choice)
            usage = _usage(data)
            structured = _structured_content(content) if request.response_schema else None
            finish_reason = str(choice.get("finish_reason") or "stop") if choice else "stop"

            if generation is not None:
                generation.update(
                    output=content,
                    usage_details={
                        "input": usage.get("input_tokens", 0),
                        "output": usage.get("output_tokens", 0),
                    },
                )

            return ChatResponse(
                provider=self.provider,
                model=str(data.get("model") or payload["model"]),
                content=content,
                structured=structured,
                latency_ms=elapsed,
                usage=usage,
                finish_reason=finish_reason,
            )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        payload = self._chat_payload(request, stream=True)
        with observe(
            f"{self.provider}-chat-stream",
            as_type="generation",
            input={"task_type": request.task_type, "messages": request.messages},
            metadata={"model": payload["model"], "provider": self.provider},
        ) as generation:
            output: list[str] = []
            usage: dict[str, Any] = {}
            async with self.client.stream("POST", self.chat_path, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    data = _parse_sse_line(line)
                    if data is None:
                        continue
                    usage = _usage(data) or usage
                    choice = _first_choice(data)
                    content = _delta_content(choice)
                    if content:
                        output.append(content)
                        yield ChatStreamChunk(content=content)
                    finish_reason = choice.get("finish_reason") if choice else None
                    if finish_reason:
                        if generation is not None:
                            generation.update(
                                output="".join(output),
                                usage_details={
                                    "input": usage.get("input_tokens", 0),
                                    "output": usage.get("output_tokens", 0),
                                },
                            )
                        yield ChatStreamChunk(finish_reason=str(finish_reason))
                        break

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        raise NotImplementedError(f"{self.provider} embeddings are not enabled")

    async def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "provider": self.provider,
            "reachable": False,
            "api_key_configured": bool(self.api_key),
            "chat_model": {"name": self.chat_model, "available": False},
            "utility_model": {"name": self.utility_model, "available": False},
            "embedding_model": {"name": None, "available": False},
        }
        if not self.api_key:
            return result
        try:
            response = await self.client.get(self.models_path)
            response.raise_for_status()
            result["reachable"] = True
            data = response.json()
            models = data.get("data", []) if isinstance(data, dict) else []
            model_ids = {
                item["id"]
                for item in models
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            result["chat_model"]["available"] = not model_ids or self.chat_model in model_ids
            result["utility_model"]["available"] = not model_ids or self.utility_model in model_ids
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        return result

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _chat_payload(self, request: ChatRequest, *, stream: bool) -> dict[str, Any]:
        messages = request.messages
        if request.response_schema and not self.supports_response_format:
            messages = [
                *messages,
                {
                    "role": "user",
                    "content": _compact_json_schema_instruction(request.response_schema),
                },
            ]
        payload: dict[str, Any] = {
            "model": request.preferred_model or self.chat_model,
            "messages": messages,
            "stream": stream,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        thinking = request.metadata.get("thinking")
        if self.provider == "longcat" and thinking in {"enabled", "disabled"}:
            payload["thinking"] = {"type": thinking}
        if request.response_schema and self.supports_response_format:
            payload["response_format"] = {"type": "json_object"}
        return payload


def _first_choice(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def _message_content(choice: dict[str, Any]) -> str:
    message = choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        return content if isinstance(content, str) else ""
    return ""


def _delta_content(choice: dict[str, Any]) -> str:
    delta = choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        return content if isinstance(content, str) else ""
    return ""


def _usage(data: dict[str, Any]) -> dict[str, Any]:
    raw_usage = data.get("usage")
    if not isinstance(raw_usage, dict):
        return {}
    usage: dict[str, Any] = {}
    if "prompt_tokens" in raw_usage:
        usage["input_tokens"] = raw_usage["prompt_tokens"]
    if "completion_tokens" in raw_usage:
        usage["output_tokens"] = raw_usage["completion_tokens"]
    if "total_tokens" in raw_usage:
        usage["total_tokens"] = raw_usage["total_tokens"]
    return usage


def _compact_json_schema_instruction(response_schema: dict[str, Any]) -> str:
    compact_schema = json.dumps(
        response_schema,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "严格按下面的压缩 JSON Schema 输出一个 JSON 对象；必填字段不得省略，"
        "不要输出解释、Markdown 或代码块：\n"
        f"{compact_schema}"
    )


def _structured_content(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line:
        return None
    payload = line.removeprefix("data:").strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
