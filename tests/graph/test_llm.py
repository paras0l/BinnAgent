from unittest.mock import AsyncMock

import pytest

from src.graph import llm
from src.providers.base import ChatResponse


@pytest.mark.asyncio
async def test_call_llm_uses_model_router(monkeypatch) -> None:
    mock_router = AsyncMock()
    mock_router.chat = AsyncMock(
        return_value=ChatResponse(provider="ollama", model="gemma4:e2b", content="summary")
    )
    monkeypatch.setattr(llm, "router", mock_router)

    result = await llm.call_llm(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        temperature=0.2,
        max_tokens=128,
    )

    assert result == "summary"
    request = mock_router.chat.await_args.args[0]
    assert request.task_type == "graph_node"
    assert request.temperature == 0.2
    assert request.max_tokens == 128
    assert request.messages == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
