import pytest

from src.providers.base import ChatRequest, EmbedRequest
from src.simulation.fake_model import DeterministicFakeModelRouter


@pytest.mark.asyncio
async def test_fake_model_returns_structured_json_for_schema() -> None:
    router = DeterministicFakeModelRouter()

    response = await router.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "generate"}],
            task_type="exercise_generate",
            response_schema={"type": "object", "properties": {"items": {"type": "array"}}},
        )
    )

    assert response.provider == "deterministic_fake"
    assert response.structured["items"][0]["correctAnswer"] == "Good morning!"
    assert response.usage["retry_count"] == 1


@pytest.mark.asyncio
async def test_fake_model_can_emit_schema_invalid_output() -> None:
    router = DeterministicFakeModelRouter()

    response = await router.chat(
        ChatRequest(
            messages=[{"role": "user", "content": "generate"}],
            task_type="exercise_generate",
            response_schema={"type": "object", "properties": {"items": {"type": "array"}}},
            metadata={"simulation_fake_output": "schema_invalid"},
        )
    )

    assert response.structured is None
    assert "grammar" in response.content


@pytest.mark.asyncio
async def test_fake_model_embed_is_deterministic() -> None:
    router = DeterministicFakeModelRouter()

    first = await router.embed(EmbedRequest(texts=["hello"]))
    second = await router.embed(EmbedRequest(texts=["hello"]))

    assert first.embeddings == second.embeddings
    assert len(first.embeddings[0]) == 8
