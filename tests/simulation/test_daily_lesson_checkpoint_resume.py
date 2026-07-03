import uuid
from datetime import datetime, timezone

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


def _task_spec(target_id: str) -> dict:
    return {
        "task_id": f"task:{target_id}",
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "objective": "Practice greeting",
        "target": {"target_type": "knowledge_point", "target_id": target_id},
        "difficulty": "easy",
        "required_inputs": [],
        "expected_output": {},
        "allowed_tools": ["exercise.grade", "mastery.update", "memory.write"],
        "success_criteria": {"min_accuracy": 1.0, "requires_explanation": True},
        "verification_policy": {
            "required_checks": [
                "task_prepared",
                "learner_answer_received",
                "exercise_attempt_created",
                "exercise_graded",
                "mastery_updated",
                "memory_event_written",
                "review_scheduled",
                "next_action_recommended",
            ],
            "require_evidence": True,
        },
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_daily_lesson_checkpoint_resume_after_restart_simulation_passes():
    learner_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    task_spec = _task_spec(target_id)
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
                    "thread_id": f"daily-lesson:{episode_id}",
                    "prompt": "Choose the greeting.",
                    "prompt_payload": {"prompt": "Choose the greeting."},
                    "required_input_schema": {"required": ["answer"]},
                    "initial_payload": {"options": ["Good morning!", "Other"]},
                    "recommendation_reason": "Mock recommendation",
                },
            )
        if request.method == "POST" and request.url.path == f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer":
            return httpx.Response(
                200,
                json={
                    "feedback": "Correct.",
                    "grading_result": {"correct": True, "score": 1.0},
                    "mastery_update": {"new_score": 0.5, "mastery_delta": 0.2},
                    "memory_updates": [{"memory_event_id": str(uuid.uuid4())}],
                    "review_schedule_result": {"status": "scheduled"},
                    "verification_status": "passed",
                    "status": "completed",
                    "checkpoint_status": "completed",
                    "recommendation_result": {"status": "recommended"},
                    "exercise_attempt_id": attempt_id,
                    "next_capability_recommendations": [],
                    "episode_id": episode_id,
                },
            )
        if request.method == "GET" and request.url.path == f"/api/runtime/episodes/{episode_id}":
            return httpx.Response(
                200,
                json={
                    "episode": {"id": episode_id, "status": "completed", "task_spec": task_spec},
                    "events": [
                        {"event_type": "graph_interrupted"},
                        {"event_type": "graph_resumed"},
                        {"event_type": "exercise_attempt_created"},
                        {"event_type": "exercise_graded"},
                        {"event_type": "mastery_updated"},
                        {"event_type": "memory_written"},
                        {"event_type": "review_scheduled"},
                        {"event_type": "next_action_recommended"},
                    ],
                    "tool_calls": [{"tool_name": "exercise.grade", "status": "success"}],
                    "checkpoint": {"checkpoint_id": checkpoint_id, "status": "completed"},
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    ) as client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["daily_lesson_checkpoint_resume_after_restart"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.runtime_metrics["completed_episode_count"] == 1
