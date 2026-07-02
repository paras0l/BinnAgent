import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.learning.orchestrator import LearningOrchestrator
from src.learning.types import LearningPlanRequest
from src.models.knowledge import CurriculumNode, ExerciseQuestion
from src.models.runtime import AgentEpisode
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy


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


def _one(value):
    return FakeResult(value=value)


def _many(values):
    return FakeResult(values=values)


def _db():
    session = AsyncMock()
    added = []
    session.add = MagicMock(side_effect=added.append)

    async def _flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(timezone.utc)
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime.now(timezone.utc)

    session.flush = AsyncMock(side_effect=_flush)
    session.added_objects = added
    return session


def _node() -> CurriculumNode:
    node = CurriculumNode(
        source_id=uuid.uuid4(),
        node_type="unit",
        title="Starter Unit 1",
        ordinal=1,
        estimated_minutes=20,
    )
    node.id = uuid.uuid4()
    node.created_at = datetime.now(timezone.utc)
    return node


def _question(node: CurriculumNode) -> ExerciseQuestion:
    question = ExerciseQuestion(
        source_id=node.source_id,
        curriculum_node_id=node.id,
        knowledge_point_id=uuid.uuid4(),
        question_type="multiple_choice",
        stem="Which answer is correct?",
        options=["Good morning!", "Other"],
        answer="Good morning!",
        explanation="Use the greeting.",
        status="published",
    )
    question.id = uuid.uuid4()
    question.created_at = datetime.now(timezone.utc)
    return question


@pytest.mark.asyncio
async def test_start_daily_lesson_selects_task_and_creates_episode():
    db = _db()
    learner_id = uuid.uuid4()
    node = _node()
    question = _question(node)
    db.execute = AsyncMock(side_effect=[_many([]), _many([]), _one(node), _one(question)])

    plan = await LearningOrchestrator(db).build_learning_plan(
        LearningPlanRequest(
            learner_id=str(learner_id),
            current_curriculum_node_id=str(node.id),
        )
    )
    started = await LearningOrchestrator(db).start_task(
        learner_id=learner_id,
        task_spec=plan.selected_task,
        recommendation_reason=plan.reason,
    )

    assert started.answer_required is True
    assert started.episode_id
    assert started.initial_payload["question_id"] == str(question.id)
    assert any(isinstance(item, AgentEpisode) for item in db.added_objects)


@pytest.mark.asyncio
async def test_submit_daily_lesson_answer_completes_existing_episode():
    db = _db()
    learner_id = uuid.uuid4()
    node = _node()
    question = _question(node)
    task_spec = TaskSpec(
        task_id=f"curriculum:{node.id}",
        task_type="practice_knowledge_point",
        source="recommendation",
        objective="Practice greeting",
        target=TaskTarget(target_type="knowledge_point", target_id=str(question.knowledge_point_id)),
        success_criteria=SuccessCriteria(min_accuracy=1.0, requires_explanation=True),
        verification_policy=VerificationPolicy(
            required_checks=[
                "exercise_attempt_saved",
                "grading_result_exists",
                "memory_event_written",
                "mastery_update_valid",
            ],
            require_evidence=True,
        ),
    )
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="waiting_user",
        task_spec=task_spec.model_dump(mode="json"),
        context_snapshot={"question_id": str(question.id)},
        tool_call_ids=[],
        started_at=datetime.now(timezone.utc),
    )
    episode.id = uuid.uuid4()
    episode.created_at = datetime.now(timezone.utc)
    episode.updated_at = datetime.now(timezone.utc)
    db.execute = AsyncMock(side_effect=[_one(episode), _one(question), _one(None)])

    result = await LearningOrchestrator(db).submit_answer(
        learner_id=learner_id,
        episode_id=episode.id,
        answer="Good morning!",
        metadata={},
    )

    assert result["episode_id"] == str(episode.id)
    assert result["verification_status"] == "passed"
    assert episode.status == "completed"
