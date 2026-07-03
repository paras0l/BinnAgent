import uuid
from datetime import datetime, timezone

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_daily_lesson_verification_failure_blocks_completed_status() -> None:
    learner_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task_spec = {
        "task_id": f"task:{target_id}",
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "objective": "Practice greeting",
        "target": {"target_type": "knowledge_point", "target_id": target_id},
        "success_criteria": {"min_accuracy": 1.0},
        "verification_policy": {
            "required_checks": ["exercise_graded", "mastery_updated"],
            "require_evidence": True,
        },
    }
    verification_report = {
        "episode_id": episode_id,
        "task_id": task_spec["task_id"],
        "status": "failed",
        "required_checks": ["exercise_graded", "mastery_updated"],
        "checks": [
            {
                "name": "exercise_graded",
                "check_type": "event",
                "passed": True,
                "severity": "critical",
                "message": "Found exercise_graded event.",
            },
            {
                "name": "mastery_updated",
                "check_type": "event",
                "passed": False,
                "severity": "critical",
                "message": "Missing event mastery_updated.",
            },
        ],
        "passed_count": 1,
        "failed_count": 1,
        "warning_count": 0,
        "critical_failed_count": 1,
        "evidence_ref_count": 1,
        "failed_reason": "Missing event mastery_updated.",
        "generated_at": now,
        "metadata": {},
    }

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
        if request.method == "POST" and request.url.path == f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer":
            return httpx.Response(
                200,
                json={
                    "feedback": "Correct.",
                    "grading_result": {"correct": True, "score": 1.0},
                    "verification_status": "failed",
                    "status": "verification_failed",
                    "checkpoint_status": "completed",
                    "episode_id": episode_id,
                },
            )
        if request.method == "GET" and request.url.path == f"/api/runtime/episodes/{episode_id}":
            return httpx.Response(
                200,
                json={
                    "episode": {
                        "id": episode_id,
                        "learner_id": learner_id,
                        "source": "recommendation",
                        "entrypoint": "daily_lesson.start",
                        "status": "verification_failed",
                        "task_spec": task_spec,
                        "started_at": now,
                        "completed_at": now,
                        "created_at": now,
                        "updated_at": now,
                    },
                    "events": [
                        {"event_type": "exercise_graded"},
                        {"event_type": "verification_report_generated"},
                    ],
                    "tool_calls": [{"tool_name": "exercise.grade", "status": "success"}],
                    "checkpoint": {"checkpoint_id": checkpoint_id, "status": "completed"},
                    "verification_report": verification_report,
                    "prompt_executions": [],
                    "evidence_refs": [{"evidence_type": "exercise_attempt", "evidence_id": target_id}],
                    "node_summaries": [],
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    ) as client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["daily_lesson_verification_failure_blocks_completed_status"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.runtime_metrics["failed_episode_count"] == 1
    assert report.runtime_metrics["verification_fail_count"] == 1
