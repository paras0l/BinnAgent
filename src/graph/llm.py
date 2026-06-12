from typing import Any

import httpx

from src.config import settings


async def call_llm(
    messages: list[dict[str, str]],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    all_messages: list[dict[str, str]] = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    payload: dict[str, Any] = {
        "model": settings.ollama_chat_model,
        "messages": all_messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url,
        timeout=httpx.Timeout(60.0),
    ) as client:
        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
