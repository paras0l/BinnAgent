import uuid
from types import SimpleNamespace

import pytest

from src.api import daily_lessons as daily_lessons_api
from src.api import deps
from src.main import app
from src.learning.types import StartedTask
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy


@pytest.fixture(autouse=True)
def daily_lesson_overrides():
    app.dependency_overrides[deps.get_db_session] = lambda: object()
    yield
    app.dependency_overrides.clear()


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_id="curriculum:node-1",
        task_type="learn_knowledge_point",
        source="recommendation",
        objective="Practice greeting",
        target=TaskTarget(target_type="curriculum_node", target_id=str(uuid.uuid4())),
        success_criteria=SuccessCriteria(min_accuracy=0.8),
        verification_policy=VerificationPolicy(required_checks=[]),
    )


@pytest.mark.asyncio
async def test_start_daily_lesson_creates_checkpoint_when_answer_required(client, monkeypatch):
    checkpoint_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    task_spec = _task_spec()

    class FakeOrchestrator:
        def __init__(self, db):
            self.db = db

        async def build_learning_plan(self, request):
            return SimpleNamespace(
                selected_task=task_spec,
                reason="继续当前教材节点。",
            )

        async def start_task(self, **kwargs):
            return StartedTask(
                episode_id=episode_id,
                task_spec=kwargs["task_spec"],
                status="waiting_user",
                answer_required=True,
                checkpoint_id=checkpoint_id,
                checkpoint_status="waiting_user",
                resume_from="generate_feedback",
                prompt="Which answer is correct?",
                initial_payload={"question_id": str(uuid.uuid4())},
                recommendation_reason="继续当前教材节点。",
            )

    monkeypatch.setattr(daily_lessons_api, "LearningOrchestrator", FakeOrchestrator)

    response = await client.post(f"/api/learners/{uuid.uuid4()}/daily-lessons/start", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_required"] is True
    assert payload["checkpoint_id"] == checkpoint_id
    assert payload["checkpoint_status"] == "waiting_user"
    assert payload["status"] == "waiting_user"


@pytest.mark.asyncio
async def test_get_daily_lesson_status_returns_waiting_checkpoint(client, monkeypatch):
    episode_id = uuid.uuid4()
    checkpoint_id = str(uuid.uuid4())

    class FakeOrchestrator:
        def __init__(self, db):
            self.db = db

        async def get_daily_lesson_status(self, **kwargs):
            return {
                "episode_id": str(kwargs["episode_id"]),
                "episode_status": "waiting_user",
                "checkpoint": {
                    "checkpoint_id": checkpoint_id,
                    "status": "waiting_user",
                    "resume_from": "generate_feedback",
                    "answer_required": True,
                    "prompt_payload": {"prompt": "Which answer is correct?"},
                    "created_at": None,
                    "consumed_at": None,
                },
                "trace_summary": {
                    "event_count": 3,
                    "tool_call_count": 0,
                    "verification_status": None,
                },
            }

    monkeypatch.setattr(daily_lessons_api, "LearningOrchestrator", FakeOrchestrator)

    response = await client.get(f"/api/learners/{uuid.uuid4()}/daily-lessons/{episode_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["episode_id"] == str(episode_id)
    assert payload["checkpoint"]["checkpoint_id"] == checkpoint_id
    assert payload["checkpoint"]["status"] == "waiting_user"
