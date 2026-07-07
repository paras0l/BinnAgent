import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.learning.orchestrator import LearningOrchestrator
from src.learning.types import LearningPlanRequest
from src.models.graph_checkpoint import LearningGraphCheckpoint
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


def _count(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


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


def _checkpoint(learner_id: uuid.UUID, episode_id: uuid.UUID, question: ExerciseQuestion) -> LearningGraphCheckpoint:
    checkpoint = LearningGraphCheckpoint(
        learner_id=learner_id,
        episode_id=episode_id,
        thread_id=f"daily-lesson:{episode_id}",
        checkpoint_key=f"{episode_id}:task",
        status="waiting_user",
        resume_from="grade_attempt",
        state_snapshot={
            "episode_id": str(episode_id),
            "learner_id": str(learner_id),
            "user_id": str(learner_id),
            "thread_id": f"daily-lesson:{episode_id}",
            "current_task_id": "task",
            "input_materials": [
                {
                    "task_id": "task",
                    "question_id": str(question.id),
                    "stem": question.stem,
                    "options": question.options or [],
                    "answer": question.answer,
                    "target_type": "knowledge_point",
                    "target_id": str(question.knowledge_point_id),
                }
            ],
            "selected_task": {
                "task_id": "task",
                "task_type": "practice_knowledge_point",
                "source": "test",
                "objective": "Practice greeting",
                "target": {
                    "target_type": "knowledge_point",
                    "target_id": str(question.knowledge_point_id),
                },
                "success_criteria": {"min_accuracy": 1.0},
                "verification_policy": {"required_checks": []},
                "metadata": {},
            },
            "answer_required": True,
        },
        required_input_schema={"required": ["answer"]},
        prompt_payload={"prompt": question.stem, "input_materials": []},
    )
    checkpoint.id = uuid.uuid4()
    checkpoint.created_at = datetime.now(timezone.utc)
    checkpoint.updated_at = checkpoint.created_at
    return checkpoint


@pytest.mark.asyncio
async def test_start_daily_lesson_selects_task_and_creates_episode():
    db = _db()
    learner_id = uuid.uuid4()
    node = _node()
    question = _question(node)
    db.execute = AsyncMock(
        side_effect=[
            _many([]),
            _many([]),
            _one(node),
            _one(question),
            _many([]),
            _one(None),
        ]
    )

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
    assert started.status == "waiting_user"
    assert started.checkpoint_id
    assert started.checkpoint_status == "waiting_user"
    assert started.resume_from == "grade_attempt"
    assert started.thread_id == f"daily-lesson:{started.episode_id}"
    assert started.prompt_payload["prompt"] == question.stem
    assert started.required_input_schema["required"] == ["answer"]
    assert started.initial_payload["question_id"] == str(question.id)
    assert any(isinstance(item, AgentEpisode) for item in db.added_objects)
    assert any(isinstance(item, LearningGraphCheckpoint) for item in db.added_objects)


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
                "task_prepared",
                "learner_answer_received",
                "exercise_attempt_created",
                "exercise_graded",
                "memory_event_written",
                "mastery_updated",
                "review_scheduled",
                "next_action_recommended",
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
    checkpoint = _checkpoint(learner_id, episode.id, question)
    db.execute = AsyncMock(
        side_effect=[
            _one(episode),
            _one(checkpoint),
            _one(question),
            _one(checkpoint),
            _one(None),
            _many([]),
            _one(checkpoint),
        ]
    )

    result = await LearningOrchestrator(db).submit_answer(
        learner_id=learner_id,
        episode_id=episode.id,
        answer="Good morning!",
        metadata={},
    )

    assert result["episode_id"] == str(episode.id)
    assert result["verification_status"] == "passed"
    assert result["checkpoint_status"] == "completed"
    assert result["exercise_attempt_id"]
    assert result["recommendation_result"]["status"] == "recommended"
    assert result["review_schedule_result"]["status"] == "scheduled"
    assert result["next_capability_recommendations"]
    assert result["next_capability_recommendations"][0]["capability_id"] == "grammar-explain"
    assert episode.status == "completed"
    assert checkpoint.status == "completed"


@pytest.mark.asyncio
async def test_submit_answer_rejects_wrong_learner():
    db = _db()
    learner_id = uuid.uuid4()
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="waiting_user",
        task_spec={},
        context_snapshot={},
        tool_call_ids=[],
        started_at=datetime.now(timezone.utc),
    )
    episode.id = uuid.uuid4()
    db.execute = AsyncMock(side_effect=[_one(episode)])

    with pytest.raises(HTTPException) as exc:
        await LearningOrchestrator(db).submit_answer(
            learner_id=uuid.uuid4(),
            episode_id=episode.id,
            answer="A",
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_answer_without_checkpoint_returns_409():
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
        verification_policy=VerificationPolicy(required_checks=[]),
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
    db.execute = AsyncMock(side_effect=[_one(episode), _one(None)])

    with pytest.raises(HTTPException) as exc:
        await LearningOrchestrator(db).submit_answer(
            learner_id=learner_id,
            episode_id=episode.id,
            answer="Good morning!",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_get_daily_lesson_status_returns_waiting_checkpoint():
    db = _db()
    learner_id = uuid.uuid4()
    node = _node()
    question = _question(node)
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="waiting_user",
        task_spec={},
        context_snapshot={},
        tool_call_ids=[],
        started_at=datetime.now(timezone.utc),
    )
    episode.id = uuid.uuid4()
    checkpoint = _checkpoint(learner_id, episode.id, question)
    db.execute = AsyncMock(
        side_effect=[
            _one(episode),
            _many([checkpoint]),
            _one(None),
            _count(3),
            _count(1),
        ]
    )

    result = await LearningOrchestrator(db).get_daily_lesson_status(
        learner_id=learner_id,
        episode_id=episode.id,
    )

    assert result["episode_status"] == "waiting_user"
    assert result["checkpoint"]["checkpoint_id"] == str(checkpoint.id)
    assert result["checkpoint"]["status"] == "waiting_user"
    assert result["trace_summary"]["event_count"] == 3


@pytest.mark.asyncio
async def test_get_daily_lesson_status_abandons_stale_waiting_checkpoint():
    db = _db()
    learner_id = uuid.uuid4()
    node = _node()
    question = _question(node)
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="waiting_user",
        task_spec={},
        context_snapshot={},
        tool_call_ids=[],
        started_at=datetime.now(timezone.utc),
    )
    episode.id = uuid.uuid4()
    checkpoint = _checkpoint(learner_id, episode.id, question)
    db.execute = AsyncMock(
        side_effect=[
            _one(episode),
            _many([checkpoint]),
            _one(uuid.uuid4()),
            _one(checkpoint),
            _count(0),
            _count(0),
        ]
    )

    result = await LearningOrchestrator(db).get_daily_lesson_status(
        learner_id=learner_id,
        episode_id=episode.id,
    )

    assert result["episode_status"] == "abandoned"
    assert result["checkpoint"]["status"] == "abandoned"
    assert result["checkpoint"]["answer_required"] is False
    assert checkpoint.consumed_at is not None
