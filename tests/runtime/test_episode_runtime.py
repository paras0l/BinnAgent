import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
from src.models.prompt_execution import PromptExecutionRecord
from src.runtime.episode import EpisodeRuntime
from src.runtime.hashing import stable_json_hash
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_id="task-1",
        task_type="practice_knowledge_point",
        source="textbook_guided",
        objective="Practice present tense",
        target=TaskTarget(target_type="knowledge_point", target_id=str(uuid.uuid4())),
        success_criteria=SuccessCriteria(min_accuracy=1.0),
        verification_policy=VerificationPolicy(required_checks=["exercise_graded"]),
    )


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


@pytest.mark.asyncio
async def test_episode_runtime_records_complete_trace():
    learner_id = uuid.uuid4()
    db = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)

    async def _flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(timezone.utc)
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime.now(timezone.utc)

    db.flush = AsyncMock(side_effect=_flush)
    runtime = EpisodeRuntime(db)

    episode = await runtime.create_episode(
        learner_id=learner_id,
        source="textbook_guided",
        entrypoint="test",
        task_spec=_task_spec(),
    )
    assert isinstance(episode, AgentEpisode)
    assert episode.status == "created"

    event = await runtime.append_event(
        episode_id=episode.id,
        learner_id=learner_id,
        event_type="exercise_graded",
        source_module="knowledge",
        target_type="knowledge_point",
        target_id=episode.task_spec["target"]["target_id"],
        payload={"score": 1.0},
    )
    assert isinstance(event, LearningEvent)

    db.execute = AsyncMock(return_value=FakeResult(episode))
    tool = await runtime.record_tool_call(
        episode_id=episode.id,
        tool_name="exercise.grade",
        input_hash=stable_json_hash({"answer": "A"}),
        output_hash=stable_json_hash({"score": 1.0}),
        latency_ms=12,
    )
    assert isinstance(tool, ToolCallRecord)
    assert str(tool.id) in episode.tool_call_ids

    completed = await runtime.complete_episode(
        episode.id,
        verification_report={"status": "passed", "checks": []},
    )
    assert completed.status == "completed"
    assert completed.verification_report["status"] == "passed"

    db.execute = AsyncMock(
        side_effect=[
            FakeResult(episode),
            FakeResult(values=[event]),
            FakeResult(values=[tool]),
            FakeResult(values=[]),
            FakeResult(None),
        ]
    )
    trace = await runtime.get_episode_trace(episode.id)
    assert trace.episode.id == str(episode.id)
    assert [item.event_type for item in trace.events] == ["exercise_graded"]
    assert [item.tool_name for item in trace.tool_calls] == ["exercise.grade"]
    assert trace.verification_report["status"] == "passed"
    assert trace.evidence_refs == []
    assert trace.prompt_executions == []


@pytest.mark.asyncio
async def test_episode_runtime_maps_verification_failed_status():
    learner_id = uuid.uuid4()
    db = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)

    async def _flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(timezone.utc)
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime.now(timezone.utc)

    db.flush = AsyncMock(side_effect=_flush)
    runtime = EpisodeRuntime(db)
    episode = await runtime.create_episode(
        learner_id=learner_id,
        source="textbook_guided",
        entrypoint="test",
        task_spec=_task_spec(),
    )

    completed = await runtime.complete_episode(
        episode.id,
        verification_report={
            "status": "failed",
            "failed_reason": "Missing event mastery_updated.",
            "checks": [],
        },
        episode=episode,
    )

    assert completed.status == "verification_failed"
    assert completed.failure_type == "verification_failed"


@pytest.mark.asyncio
async def test_episode_trace_includes_prompt_executions_and_graph_run():
    learner_id = uuid.uuid4()
    episode_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="completed",
        task_spec=_task_spec().model_dump(mode="json"),
        context_snapshot={
            "thread_id": f"daily-lesson:{episode_id}",
            "graph_run_id": "graph-run-1",
            "current_task_id": "task-1",
            "checkpoint_status": "completed",
        },
        verification_report={"status": "passed", "checks": []},
        started_at=now,
        completed_at=now,
    )
    episode.id = episode_id
    episode.created_at = now
    episode.updated_at = now
    event = LearningEvent(
        episode_id=episode_id,
        learner_id=learner_id,
        event_type="exercise_graded",
        source_module="daily_lesson",
        target_type="knowledge_point",
        target_id=str(uuid.uuid4()),
        payload={
            "evidence_refs": [
                {"evidence_type": "exercise_attempt", "evidence_id": str(uuid.uuid4())}
            ]
        },
        occurred_at=now,
    )
    event.id = uuid.uuid4()
    event.created_at = now
    prompt = PromptExecutionRecord(
        learner_id=learner_id,
        episode_id=episode_id,
        task_id="task-1",
        source_module="daily_lesson",
        prompt_id="daily.feedback",
        prompt_version="v1",
        prompt_hash="a" * 64,
        input_hash="b" * 64,
        output_schema="Feedback",
        model_policy_snapshot={},
        schema_validation_status="valid",
        repair_used=False,
        fallback_used=False,
        parse_mode="json",
        decision="accepted",
    )
    prompt.id = uuid.uuid4()
    prompt.created_at = now
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            FakeResult(episode),
            FakeResult(values=[event]),
            FakeResult(values=[]),
            FakeResult(values=[prompt]),
            FakeResult(None),
        ]
    )

    trace = await EpisodeRuntime(db).get_episode_trace(episode_id)

    assert trace.graph_run["graph_run_id"] == "graph-run-1"
    assert trace.prompt_executions[0].prompt_id == "daily.feedback"
    assert trace.evidence_refs[0].evidence_type == "exercise_attempt"
    assert trace.node_summaries[0]["node"] == "daily_lesson"
