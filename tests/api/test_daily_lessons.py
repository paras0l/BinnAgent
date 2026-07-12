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
    app.dependency_overrides[deps.get_current_learner] = lambda: SimpleNamespace(
        id=uuid.uuid4()
    )
    app.dependency_overrides[deps.get_model_router] = lambda: object()
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
                resume_from="grade_attempt",
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
                    "resume_from": "grade_attempt",
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


@pytest.mark.asyncio
async def test_compose_classroom_returns_generative_ui_spec(client, monkeypatch):
    node_id = uuid.uuid4()

    async def fake_compose(db, model_router, **kwargs):
        assert kwargs["curriculum_node_id"] == node_id
        return {
            "schema_version": "1.0",
            "classroom_id": f"{node_id}:v1",
            "generation_mode": "llm_generated",
            "phases": [{"id": "launch", "kind": "briefing", "title": "入场", "minutes": 2}],
        }

    monkeypatch.setattr(daily_lessons_api, "compose_classroom", fake_compose)
    response = await client.post(
        f"/api/learners/{uuid.uuid4()}/daily-lessons/classroom/compose",
        json={"curriculum_node_id": str(node_id), "time_budget_minutes": 20},
    )

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "llm_generated"
    assert response.json()["phases"][0]["kind"] == "briefing"


@pytest.mark.asyncio
async def test_classroom_progress_is_saved_for_current_learner(client, monkeypatch):
    node_id = uuid.uuid4()
    classroom_id = f"{node_id}:v1"
    captured = {}

    async def fake_save(db, **kwargs):
        captured.update(kwargs)
        return {"classroom_id": classroom_id, "status": "in_progress", "saved_at": "now"}

    monkeypatch.setattr(daily_lessons_api, "save_classroom_progress", fake_save)
    response = await client.put(
        f"/api/learners/{uuid.uuid4()}/daily-lessons/classroom/progress",
        json={
            "curriculum_node_id": str(node_id),
            "classroom_id": classroom_id,
            "current_phase_id": "listen",
            "completed_phase_ids": ["launch", "notice"],
            "flipped_card_ids": ["word-0"],
            "listened_cue_ids": ["cue-001"],
            "grammar_answers": {"g1": "am"},
            "grammar_transfer": "I am in Class 1.",
            "vocabulary_confidence": {"word-0": "known"},
            "continuous_audio_played": True,
            "completed": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert captured["current_phase_id"] == "listen"
    assert captured["completed_phase_ids"] == ["launch", "notice"]
    assert captured["listened_cue_ids"] == ["cue-001"]
    assert captured["grammar_answers"] == {"g1": "am"}
    assert captured["grammar_transfer"] == "I am in Class 1."
    assert captured["vocabulary_confidence"] == {"word-0": "known"}
    assert captured["continuous_audio_played"] is True


@pytest.mark.asyncio
async def test_classroom_timeline_exposes_reviewed_sentence_cues(client):
    response = await client.get(
        f"/api/learners/{uuid.uuid4()}/daily-lessons/classroom/timeline/01-Starter-Unit-1-Hello.mp3"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["calibration"]["status"] == "reviewed"
    assert payload["cue_count"] == 186
    assert payload["cues"][0]["start_ms"] == 0


@pytest.mark.asyncio
async def test_classroom_coach_uses_current_learner_and_textbook_answer(client, monkeypatch):
    node_id = uuid.uuid4()
    captured = {}

    async def fake_coach(db, model_router, **kwargs):
        captured.update(kwargs)
        return {
            "diagnosis": "1a 还没有完成全部匹配。",
            "evidence": ["只填写了 Peter"],
            "hint": "按头像从左到右检查。",
            "next_action": "continue",
            "generation_mode": "llm_generated",
        }

    monkeypatch.setattr(daily_lessons_api, "coach_textbook_task", fake_coach)
    response = await client.post(
        f"/api/learners/{uuid.uuid4()}/daily-lessons/classroom/coach",
        json={"curriculum_node_id": str(node_id), "task_id": "unit-1-section-a", "answer": "1a: Peter"},
    )

    assert response.status_code == 200
    assert response.json()["generation_mode"] == "llm_generated"
    assert captured["curriculum_node_id"] == node_id
    assert captured["answer"] == "1a: Peter"
