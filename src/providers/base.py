from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ChatRequest:
    messages: list[dict[str, str]]
    task_type: str = "general"
    temperature: float = 0.3
    max_tokens: int = 2000
    response_schema: dict[str, Any] | None = None
    preferred_provider: str = "ollama"
    preferred_model: str | None = None
    local_only: bool = True


@dataclass
class ChatResponse:
    provider: str
    model: str
    content: str
    structured: dict[str, Any] | None = None
    latency_ms: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


@runtime_checkable
class ModelClient(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    async def health_check(self) -> dict[str, Any]: ...
