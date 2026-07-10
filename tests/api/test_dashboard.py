import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.error_pattern import ErrorPattern
from src.models.knowledge import ExerciseAttempt, LearnerKnowledgeState
from src.models.learning_progress import LearningProgressItem
from src.models.session import LearningSession
from src.models.vocabulary import ReviewSchedule, VocabularyItem, VocabularyMasteryVector


@pytest.fixture
def mock_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _count(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_dashboard_profile_uses_real_backend_evidence(client, mock_session):
    learner_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    today = now.date()

    vocab = VocabularyItem(
        learner_id=learner_id,
        word="careful",
        canonical_key="careful",
        meanings=[{"definition": "小心的"}],
        examples=[{"sentence": "Be careful."}],
        status="learning",
        confidence=0.6,
        next_review_at=now - timedelta(minutes=5),
    )
    vocab.id = uuid.uuid4()

    mastered_vocab = VocabularyItem(
        learner_id=learner_id,
        word="hello",
        canonical_key="hello",
        status="mastered",
        confidence=0.95,
        next_review_at=now + timedelta(days=3),
    )
    mastered_vocab.id = uuid.uuid4()

    knowledge_state = LearnerKnowledgeState(
        learner_id=learner_id,
        knowledge_point_id=uuid.uuid4(),
        mastery_score=0.25,
        confidence=0.25,
    )
    knowledge_state.id = uuid.uuid4()

    vector = VocabularyMasteryVector(
        learner_id=learner_id,
        vocabulary_item_id=vocab.id,
        recognition=0.8,
        recall=0.7,
        spelling=0.6,
        listening=0.5,
        context_use=0.7,
        production=0.6,
    )
    vector.id = uuid.uuid4()

    grammar_progress = LearningProgressItem(
        learner_id=learner_id,
        skill="grammar",
        item_id="present-simple",
        title="一般现在时",
        status="learned",
        opened_count=2,
    )
    grammar_progress.id = uuid.uuid4()

    reading_attempt = ExerciseAttempt(
        learner_id=learner_id,
        submitted_answer="A",
        correct=False,
        exercise_id="reading-1",
        target_type="reading",
        target_id="unit-1",
        target_label="Unit 1 reading",
        answer="B",
        result="incorrect",
        metadata_={},
        source_context={},
    )
    reading_attempt.id = uuid.uuid4()
    reading_attempt.created_at = now

    grammar_attempt = ExerciseAttempt(
        learner_id=learner_id,
        submitted_answer="does",
        correct=True,
        exercise_id="grammar-1",
        target_type="grammar",
        target_id="present-simple",
        target_label="一般现在时",
        answer="does",
        result="correct",
        metadata_={},
        source_context={},
    )
    grammar_attempt.id = uuid.uuid4()
    grammar_attempt.created_at = now

    review = ReviewSchedule(
        learner_id=learner_id,
        item_type="vocabulary",
        item_id=vocab.id,
        scheduled_at=now - timedelta(hours=1),
        completed_at=now,
        result="correct",
    )
    review.id = uuid.uuid4()

    session = LearningSession(
        learner_id=learner_id,
        session_type="daily_lesson",
        status="completed",
        completed_at=now,
    )
    session.id = uuid.uuid4()

    error_pattern = ErrorPattern(
        learner_id=learner_id,
        skill="reading",
        pattern="细节定位不稳定",
        frequency=2,
        severity="medium",
    )
    error_pattern.id = uuid.uuid4()

    mock_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _count(2),
            _count(1),
            _many([review]),
            _count(1),
            _many([session]),
            _many([vocab]),
            _many([error_pattern]),
            _many([vocab, mastered_vocab]),
            _many([knowledge_state]),
            _many([vector]),
            _many([grammar_progress]),
            _many([reading_attempt, grammar_attempt]),
            _many([review]),
            _many([review]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["review_items"][0]["word"] == "careful"
    assert data["error_patterns"][0]["name"] == "细节定位不稳定"
    assert data["daily_activity"][-1]["date"] == today.isoformat()
    assert data["stats"]["today_ai_conversations"] == 1

    profile = data["profile"]
    ability_scores = {item["label"]: item for item in profile["ability_scores"]}
    assert ability_scores["词汇"]["evidence_count"] == 3
    assert ability_scores["语法"]["value"] == 100
    assert ability_scores["阅读"]["value"] == 0
    assert ability_scores["听力"]["value"] == 50
    assert {bucket["label"] for bucket in profile["mastery_buckets"]} == {
        "新学",
        "学习中",
        "熟悉",
        "掌握",
    }
    assert profile["trend"][-1]["accuracy"] == 67
    assert profile["trend"][-1]["due_reviews"] == 1
