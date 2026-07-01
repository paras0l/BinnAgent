import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.providers.base import ChatResponse


@pytest.fixture
def exercise_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


@pytest.fixture
def mock_model_router():
    router = AsyncMock()
    app.dependency_overrides[deps.get_model_router] = lambda: router
    yield router
    app.dependency_overrides.pop(deps.get_model_router, None)


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_generate_exercises_returns_generated_exercise_items(
    client,
    exercise_session,
    mock_model_router,
):
    learner_id = uuid.uuid4()
    exercise_session.execute = AsyncMock(return_value=_one(learner_id))
    mock_model_router.chat.return_value = ChatResponse(
        provider="test",
        model="test",
        content="{}",
        structured={
            "items": [
                {
                    "skill": "grammar",
                    "type": "single_choice",
                    "prompt": "Which sentence is correct?",
                    "options": ["If it rains, I will stay home.", "If it will rain, I stay home."],
                    "correctAnswer": "If it rains, I will stay home.",
                    "acceptedAnswers": [],
                    "explanation": "条件状语从句中 if 从句用一般现在时表示将来。",
                    "difficulty": "easy",
                    "metadata": {"focus": "present_for_future"},
                }
            ]
        },
    )

    response = await client.post(
        f"/api/learners/{learner_id}/exercises/generate",
        json={
            "target": {
                "type": "grammar_topic",
                "id": "present-for-future",
                "label": "主将从现",
            },
            "count": 1,
            "exerciseTypes": ["single_choice"],
            "context": {"page": "GrammarPage", "learnerLevel": "junior"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["target"] == {
        "type": "grammar_topic",
        "id": "present-for-future",
        "label": "主将从现",
    }
    assert item["source"] == {"type": "generated", "name": "ai_generated"}
    assert item["metadata"]["generatedBy"] == "ai"
    assert item["metadata"]["targetType"] == "grammar_topic"
    assert item["metadata"]["targetId"] == "present-for-future"
    assert item["type"] == "single_choice"
    assert item["correctAnswer"] in item["options"]
