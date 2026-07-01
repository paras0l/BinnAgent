import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.knowledge import ExerciseAttempt


@pytest.fixture
def mock_session():
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.added_objects = added_objects
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _attempt(
    learner_id: uuid.UUID,
    attempt_id: str,
    result: str,
    created_at: datetime,
    target_id: str = "present-for-future",
) -> ExerciseAttempt:
    return ExerciseAttempt(
        id=uuid.uuid4(),
        learner_id=learner_id,
        question_id=None,
        session_id=None,
        submitted_answer=result,
        correct=result == "correct",
        response_time_ms=None,
        exercise_id=f"exercise-{attempt_id}",
        target_type="grammar_topic",
        target_id=target_id,
        target_label="主将从现",
        answer=result,
        result=result,
        metadata_={},
        source_context={},
        created_at=created_at,
        should_update_mastery=True,
        should_create_error_pattern=result == "incorrect",
        should_create_memory_evidence=True,
    )


class TestExerciseAttempts:
    @pytest.mark.asyncio
    async def test_summary_empty_returns_not_started(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.get(
            f"/api/learners/{learner_id}/exercise-attempts/summary",
            params={"target_type": "grammar_topic", "target_id": "present-for-future"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "accuracy": 0,
            "lastAttemptAt": None,
            "lastResult": None,
            "needsReview": False,
            "learningStatus": "not_started",
        }

    @pytest.mark.asyncio
    async def test_summary_marks_latest_incorrect_for_review(self, client, mock_session):
        learner_id = uuid.uuid4()
        attempts = [
            _attempt(
                learner_id,
                "a-latest",
                "incorrect",
                datetime(2026, 6, 30, 10, 2, tzinfo=timezone.utc),
            ),
            _attempt(
                learner_id,
                "a-older",
                "correct",
                datetime(2026, 6, 30, 10, 1, tzinfo=timezone.utc),
            ),
        ]
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many(attempts)])

        response = await client.get(
            f"/api/learners/{learner_id}/exercise-attempts/summary",
            params={"target_type": "grammar_topic", "target_id": "present-for-future"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "total": 2,
            "correct": 1,
            "incorrect": 1,
            "accuracy": 50,
            "lastAttemptAt": "2026-06-30T10:02:00Z",
            "lastResult": "incorrect",
            "needsReview": True,
            "learningStatus": "needs_review",
        }

    @pytest.mark.asyncio
    async def test_create_attempt_accepts_frontend_payload(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.post(
            f"/api/learners/{learner_id}/exercise-attempts",
            json={
                "id": "attempt-frontend-1",
                "exerciseId": "grammar-present-for-future-1",
                "target": {
                    "type": "grammar_topic",
                    "id": "present-for-future",
                    "label": "主将从现",
                },
                "answer": "will visit",
                "result": "correct",
                "createdAt": "2026-06-30T10:03:00.000Z",
                "should_update_mastery": True,
                "should_create_error_pattern": False,
                "should_create_memory_evidence": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["exerciseId"] == "grammar-present-for-future-1"
        assert data["target"] == {
            "type": "grammar_topic",
            "id": "present-for-future",
            "label": "主将从现",
        }
        assert data["metadata"]["client_attempt_id"] == "attempt-frontend-1"
        created = mock_session.added_objects[0]
        assert isinstance(created, ExerciseAttempt)
        assert created.learner_id == learner_id
        assert created.target_type == "grammar_topic"
        assert created.should_update_mastery is True
        assert created.metadata_["client_attempt_id"] == "attempt-frontend-1"
