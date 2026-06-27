import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
import src.api.essay_review as essay_review_api
from src.main import app
from src.models.error_pattern import ErrorPattern
from src.models.memory import LearningMemoryEvent
from src.tools.essay_scoring import EssayScoringResult


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_essay_review_uses_memory_and_writes_events(client, mock_session, monkeypatch):
    learner_id = uuid.uuid4()
    pattern = ErrorPattern(
        learner_id=learner_id,
        skill="writing",
        pattern="weak_transition",
        description="递进表达较单一",
        frequency=3,
        confidence=0.8,
        status="active",
        evidence_refs=["essay_feedback:old"],
    )
    pattern.id = uuid.uuid4()
    mock_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _many([]),
            _one(None),
            _many([]),
            _many([]),
            _many([]),
            _many([pattern]),
            _many([]),
            _many([]),
        ]
    )
    monkeypatch.setattr(
        essay_review_api.essay_scorer,
        "score",
        AsyncMock(
            return_value=EssayScoringResult(
                score=18,
                max_score=25,
                strengths=["Clear topic"],
                key_issues=["transition expressions are repetitive"],
                sentence_feedback=[],
            )
        ),
    )

    response = await client.post(
        f"/api/learners/{learner_id}/essay-review",
        json={
            "text": " ".join(["Learning English is important."] * 40),
            "prompt": "My English learning",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 18
    assert data["historical_weaknesses"][0]["summary"] == "递进表达较单一"
    assert data["memory_context"]["retrieval_reason"] == "essay_review"
    added_events = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if isinstance(call.args[0], LearningMemoryEvent)
    ]
    assert [event.event_type for event in added_events] == [
        "essay_submitted",
        "essay_feedback_received",
        "chat_error_observed",
    ]
