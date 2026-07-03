import uuid
from datetime import datetime, timezone

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_daily_lesson_missing_answer_must_not_write_memory_simulation_passes():
    learner_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    task_spec = {
        "task_id": f"task:{target_id}",
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "objective": "Practice greeting",
        "target": {"target_type": "knowledge_point", "target_id": target_id},
        "success_criteria": {"min_accuracy": 1.0},
        "verification_policy": {"required_checks": []},
    }
    now = datetime.now(timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/learners":
            return httpx.Response(201, json={"id": learner_id, "nickname": "sim"})
        if request.method == "GET" and request.url.path == "/api/recommendations/daily-plan":
            return httpx.Response(
                200,
                json={
                    "plan_id": "plan:sim",
                    "learner_id": learner_id,
                    "mode": "textbook_guided",
                    "reason": "Mock recommendation",
                    "confidence": 0.9,
                    "tasks": [{"task_spec": task_spec, "priority_score": 0.9, "reason": "Practice"}],
                    "evidence_refs": [],
                    "generated_at": now,
                },
            )
        if request.method == "POST" and request.url.path == f"/api/learners/{learner_id}/daily-lessons/start":
            return httpx.Response(
                200,
                json={
                    "episode_id": episode_id,
                    "task_spec": task_spec,
                    "status": "waiting_user",
                    "answer_required": True,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_status": "waiting_user",
                    "resume_from": "grade_attempt",
                    "prompt": "Choose the greeting.",
                    "initial_payload": {"options": ["Good morning!", "Other"]},
                },
            )
        if request.method == "GET" and request.url.path == f"/api/runtime/episodes/{episode_id}":
            return httpx.Response(
                200,
                json={
                    "episode": {"id": episode_id, "status": "waiting_user", "task_spec": task_spec},
                    "events": [
                        {"event_type": "episode_started"},
                        {"event_type": "task_prepared"},
                        {"event_type": "graph_interrupted"},
                    ],
                    "tool_calls": [],
                    "checkpoint": {"checkpoint_id": checkpoint_id, "status": "waiting_user"},
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    ) as client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["daily_lesson_missing_answer_must_not_write_memory"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    event_types = report.steps[-1].output["episode_trace_event_types"]
    assert report.status == "passed"
    assert "memory_written" not in event_types
    assert report.metrics["memory_write_count"] == 0
