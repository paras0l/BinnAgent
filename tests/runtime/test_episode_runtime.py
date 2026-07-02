import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
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
        ]
    )
    trace = await runtime.get_episode_trace(episode.id)
    assert trace.episode.id == str(episode.id)
    assert [item.event_type for item in trace.events] == ["exercise_graded"]
    assert [item.tool_name for item in trace.tool_calls] == ["exercise.grade"]
