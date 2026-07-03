from __future__ import annotations

import json
from typing import Any, AsyncIterator

from src.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbedRequest,
    EmbedResponse,
)


class DeterministicFakeModelRouter:
    """Deterministic model router for integration simulations."""

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        fake_mode = str(request.metadata.get("simulation_fake_output") or "")
        if fake_mode == "schema_invalid":
            return _response({"items": [{"skill": "grammar"}]}, structured=False)
        if fake_mode == "repair" or request.task_type == "exercise_generate":
            return _response(
                _exercise_payload(),
                usage={"retry_count": 1, "repair_reason": "missing_required_field"},
            )
        if request.response_schema:
            return _response(_payload_for_schema(request.response_schema, request.task_type))
        return ChatResponse(
            provider="deterministic_fake",
            model="simulation",
            content="This is a deterministic simulation response.",
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        response = await self.chat(request)
        yield ChatStreamChunk(content=response.content, finish_reason=response.finish_reason)

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        return EmbedResponse(
            provider="deterministic_fake",
            model="simulation-embed",
            embeddings=[_embedding(text) for text in request.texts],
        )

    async def health_check(self) -> dict[str, Any]:
        return {"deterministic_fake": {"status": "ok", "requests": len(self.requests)}}


def _response(
    payload: dict[str, Any],
    *,
    structured: bool = True,
    usage: dict[str, Any] | None = None,
) -> ChatResponse:
    return ChatResponse(
        provider="deterministic_fake",
        model="simulation",
        content=json.dumps(payload, ensure_ascii=False),
        structured=payload if structured else None,
        usage=usage or {},
    )


def _payload_for_schema(schema: dict[str, Any], task_type: str) -> dict[str, Any]:
    properties = schema.get("properties") if isinstance(schema, dict) else {}
    if isinstance(properties, dict) and "items" in properties:
        return _exercise_payload()
    if isinstance(properties, dict) and "cards" in properties:
        return {
            "cards": [
                {
                    "word": "significant",
                    "phonetic": "/sɪɡˈnɪfɪkənt/",
                    "definition_zh": "重要的",
                    "definition_en": "important enough to matter",
                    "examples": [{"sentence": "This is significant."}],
                    "confidence": 0.9,
                }
            ]
        }
    if isinstance(properties, dict) and "candidates" in properties:
        return {
            "candidates": [
                {
                    "text": "What matters most is that...",
                    "examples": [{"sentence": "What matters most is that we keep learning."}],
                    "quality_score": 0.86,
                }
            ]
        }
    return {"message": f"deterministic output for {task_type}"}


def _exercise_payload() -> dict[str, Any]:
    return {
        "items": [
            {
                "skill": "vocabulary",
                "type": "single_choice",
                "prompt": "Which expression is a morning greeting?",
                "options": ["Good morning!", "Good night!", "Thank you."],
                "correctAnswer": "Good morning!",
                "explanation": "Good morning is used as a morning greeting.",
                "difficulty": "easy",
                "metadata": {"simulation_repair_used": True},
            }
        ]
    }


def _embedding(text: str) -> list[float]:
    seed = sum(ord(char) for char in text)
    return [((seed + index) % 101) / 100 for index in range(8)]
