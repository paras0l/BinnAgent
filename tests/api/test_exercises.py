import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.prompt_execution import PromptExecutionRecord
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
        content=(
            '{"items":[{"skill":"grammar","type":"grammar_fill_blank",'
            '"prompt":"If it ____ tomorrow, I will stay home.","options":[],'
            '"correctAnswer":"rains","acceptedAnswers":["rains"],'
            '"explanation":"条件状语从句中 if 从句用一般现在时表示将来。",'
            '"difficulty":"easy","metadata":{"focus":"present_for_future"}}]}'
        ),
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
            "exerciseTypes": ["grammar_fill_blank"],
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
    assert item["type"] == "grammar_fill_blank"
    assert item["acceptedAnswers"] == ["rains"]
    request = mock_model_router.chat.call_args.args[0]
    assert request.task_type == "exercise.generate"
    assert request.response_schema is not None
    added_record = exercise_session.add.call_args.args[0]
    assert isinstance(added_record, PromptExecutionRecord)
    assert added_record.prompt_id == "exercise.generate"
    assert added_record.decision == "accepted"


@pytest.mark.asyncio
async def test_generate_exercises_defaults_to_grammar_fill_blank_for_grammar_topics(
    client,
    exercise_session,
    mock_model_router,
):
    learner_id = uuid.uuid4()
    exercise_session.execute = AsyncMock(return_value=_one(learner_id))
    mock_model_router.chat.return_value = ChatResponse(
        provider="test",
        model="test",
        content=(
            '{"items":[{"skill":"grammar","type":"fill_blank",'
            '"prompt":"She ____ English every day.","correctAnswer":"studies",'
            '"explanation":"一般现在时第三人称单数动词用 studies。",'
            '"difficulty":"easy"}]}'
        ),
    )

    response = await client.post(
        f"/api/learners/{learner_id}/exercises/generate",
        json={
            "target": {
                "type": "grammar_topic",
                "id": "simple-present",
                "label": "一般现在时",
            },
            "count": 1,
        },
    )

    assert response.status_code == 200
    assert "grammar_fill_blank" in mock_model_router.chat.call_args.args[0].messages[0]["content"]


@pytest.mark.asyncio
async def test_generate_exercises_rejects_schema_invalid_output(
    client,
    exercise_session,
    mock_model_router,
):
    learner_id = uuid.uuid4()
    exercise_session.execute = AsyncMock(return_value=_one(learner_id))
    mock_model_router.chat.return_value = ChatResponse(
        provider="test",
        model="test",
        content='{"items":[{"prompt":"I have ___ apple."}]}',
    )

    response = await client.post(
        f"/api/learners/{learner_id}/exercises/generate",
        json={
            "target": {
                "type": "grammar_topic",
                "id": "article-a-an",
                "label": "冠词 a/an",
            },
            "count": 1,
        },
    )

    assert response.status_code == 502
    added_record = exercise_session.add.call_args.args[0]
    assert isinstance(added_record, PromptExecutionRecord)
    assert added_record.prompt_id == "exercise.generate"
    assert added_record.decision == "rejected"
