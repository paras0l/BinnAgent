import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.models.knowledge import LearnerKnowledgeState
from src.models.vocabulary import ReviewSchedule
from src.recommendation.engine import RecommendationEngine
from src.recommendation.types import RecommendationInput


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeResult:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = [] if values is None else values

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return FakeScalarResult(self.values)


def _many(values):
    return FakeResult(values=values)


@pytest.mark.asyncio
async def test_empty_learning_data_returns_textbook_guided_empty_plan():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_many([]), _many([])])

    plan = await RecommendationEngine(db).build_daily_plan(
        RecommendationInput(learner_id=str(uuid.uuid4()))
    )

    assert plan.mode == "textbook_guided"
    assert plan.tasks == []


@pytest.mark.asyncio
async def test_low_mastery_state_recommends_repair_weakness():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    state = LearnerKnowledgeState(
        learner_id=learner_id,
        knowledge_point_id=point_id,
        status="reviewing",
        mastery_score=0.25,
        confidence=0.7,
        exposure_count=3,
        correct_count=1,
        evidence_summary={},
    )
    state.id = uuid.uuid4()
    state.updated_at = datetime.now(timezone.utc)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_many([]), _many([state])])

    plan = await RecommendationEngine(db).build_daily_plan(
        RecommendationInput(learner_id=str(learner_id))
    )

    assert plan.mode == "weakness_repair"
    assert plan.tasks[0].task_spec.task_type == "repair_weakness"
    assert plan.tasks[0].task_spec.target.target_id == str(point_id)
    assert plan.tasks[0].evidence_refs[0].evidence_type == "knowledge_point"


@pytest.mark.asyncio
async def test_due_review_recommends_review_due_item():
    learner_id = uuid.uuid4()
    point_id = uuid.uuid4()
    review = ReviewSchedule(
        learner_id=learner_id,
        item_type="knowledge",
        item_id=point_id,
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    review.id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_many([review]), _many([])])

    plan = await RecommendationEngine(db).build_daily_plan(
        RecommendationInput(learner_id=str(learner_id))
    )

    assert plan.mode == "review"
    assert plan.tasks[0].task_spec.task_type == "review_due_item"
    assert plan.tasks[0].priority_score == 0.8


@pytest.mark.asyncio
async def test_priority_sorting_is_stable_and_tasks_include_task_spec():
    learner_id = uuid.uuid4()
    review_a = ReviewSchedule(
        learner_id=learner_id,
        item_type="knowledge",
        item_id=uuid.uuid4(),
        scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    review_b = ReviewSchedule(
        learner_id=learner_id,
        item_type="knowledge",
        item_id=uuid.uuid4(),
        scheduled_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    review_a.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    review_b.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_many([review_b, review_a]), _many([])])

    plan = await RecommendationEngine(db).build_daily_plan(
        RecommendationInput(learner_id=str(learner_id))
    )

    assert [task.task_spec.task_id for task in plan.tasks] == [
        f"review:{review_a.id}",
        f"review:{review_b.id}",
    ]
    assert all(task.task_spec.verification_policy.require_evidence for task in plan.tasks)
