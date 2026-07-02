import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mastery.engine import MasteryEngine
from src.mastery.types import AttemptSignal
from src.models.knowledge import LearnerKnowledgeState


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _db_with_state(state=None):
    db = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)
    db.execute = AsyncMock(return_value=FakeResult(state))

    async def _flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    db.flush = AsyncMock(side_effect=_flush)
    db.added_objects = added
    return db


def _signal(**overrides) -> AttemptSignal:
    payload = {
        "learner_id": str(uuid.uuid4()),
        "target_type": "knowledge_point",
        "target_id": str(uuid.uuid4()),
        "correct": True,
        "score": 1.0,
        "error_type": None,
        "hint_count": 0,
        "retry_count": 0,
        "response_time_ms": 1200,
        "source": "test",
    }
    payload.update(overrides)
    return AttemptSignal(**payload)


def _state(learner_id: uuid.UUID, point_id: uuid.UUID, score: float) -> LearnerKnowledgeState:
    state = LearnerKnowledgeState(
        learner_id=learner_id,
        knowledge_point_id=point_id,
        status="learning",
        mastery_score=score,
        confidence=0.4,
        exposure_count=2,
        correct_count=1,
        evidence_summary={},
    )
    state.id = uuid.uuid4()
    state.created_at = datetime.now(timezone.utc)
    return state


@pytest.mark.asyncio
async def test_correct_attempt_increases_mastery_score():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    state = _state(learner_id, point_id, 0.3)

    result = await MasteryEngine(_db_with_state(state)).update_from_attempt(
        _signal(learner_id=str(learner_id), target_id=str(point_id), correct=True, score=1.0)
    )

    assert result.new_score > result.previous_score
    assert 0 <= result.new_score <= 1


@pytest.mark.asyncio
async def test_incorrect_attempt_adds_weakness_tag_and_lowers_mastery():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    state = _state(learner_id, point_id, 0.5)

    result = await MasteryEngine(_db_with_state(state)).update_from_attempt(
        _signal(
            learner_id=str(learner_id),
            target_id=str(point_id),
            correct=False,
            score=0.2,
            error_type="missing_target_expression",
        )
    )

    assert result.new_score < result.previous_score
    assert result.weakness_tags == ["missing_target_expression"]


@pytest.mark.asyncio
async def test_high_hint_count_reduces_mastery_gain():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    low_hint_state = _state(learner_id, point_id, 0.3)
    high_hint_state = _state(learner_id, point_id, 0.3)

    low_hint = await MasteryEngine(_db_with_state(low_hint_state)).update_from_attempt(
        _signal(learner_id=str(learner_id), target_id=str(point_id), hint_count=0)
    )
    high_hint = await MasteryEngine(_db_with_state(high_hint_state)).update_from_attempt(
        _signal(learner_id=str(learner_id), target_id=str(point_id), hint_count=5)
    )

    assert high_hint.mastery_delta < low_hint.mastery_delta


@pytest.mark.asyncio
async def test_mastery_score_is_clamped_to_zero_one():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    state = _state(learner_id, point_id, 0.95)

    result = await MasteryEngine(_db_with_state(state)).update_from_attempt(
        _signal(learner_id=str(learner_id), target_id=str(point_id), correct=True, score=1.0)
    )

    assert result.new_score == 1.0
