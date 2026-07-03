import uuid
from datetime import datetime, timezone

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


def _task_spec(task_id: str, target_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "objective": "Practice greeting",
        "target": {
            "target_type": "knowledge_point",
            "target_id": target_id,
            "label": "Greeting",
            "metadata": {},
        },
        "difficulty": "easy",
        "required_inputs": [],
        "expected_output": {},
        "allowed_tools": ["exercise.grade", "mastery.update", "memory.write"],
        "success_criteria": {
            "min_accuracy": 1.0,
            "max_hint_count": None,
            "requires_explanation": True,
            "required_outputs": [],
        },
        "verification_policy": {
            "required_checks": ["exercise_graded", "mastery_update_valid"],
            "allow_llm_judge": False,
            "require_evidence": True,
        },
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_episode_runtime_simulation_reports_runtime_metrics():
    learner_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    recommendation_id = "caprec:simulation"
    task_spec = _task_spec(f"task:{target_id}", target_id)
    capability_recommendation = {
        "recommendation_id": recommendation_id,
        "capability_id": "grammar-explain",
        "feature_id": "grammar-explain",
        "title": "语法微知识点",
        "reason": "本次练习暴露了语法规则混淆，适合马上补一个专项入口。",
        "priority_score": 0.86,
        "category": "grammar",
        "action": "tool",
        "tool_target": "grammar",
        "route_hint": None,
        "prompt_seed": None,
        "input_payload": {},
        "evidence_refs": [{"type": "exercise_question", "id": target_id}],
        "source": "rule",
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
                    "tasks": [
                        {
                            "task_spec": task_spec,
                            "priority_score": 0.9,
                            "reason": "Practice the next knowledge point.",
                            "evidence_refs": [],
                            "estimated_minutes": 5,
                        }
                    ],
                    "evidence_refs": [],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
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
                    "resume_from": "generate_feedback",
                    "prompt": "Choose the greeting.",
                    "initial_payload": {
                        "question_id": str(uuid.uuid4()),
                        "options": ["Good morning!", "Other"],
                    },
                    "recommendation_reason": "Mock recommendation",
                },
            )
        if request.method == "POST" and request.url.path == f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer":
            return httpx.Response(
                200,
                json={
                    "feedback": "Correct.",
                    "grading_result": {"correct": True, "score": 1.0},
                    "mastery_update": {"new_score": 0.4},
                    "memory_updates": [{"memory_event_id": str(uuid.uuid4())}],
                    "verification_status": "passed",
                    "status": "completed",
                    "checkpoint_status": "completed",
                    "next_recommendation": None,
                    "next_capability_recommendations": [capability_recommendation],
                    "episode_id": episode_id,
                },
            )
        if (
            request.method == "POST"
            and request.url.path
            == f"/api/learners/{learner_id}/explore/capabilities/grammar-explain/events"
        ):
            return httpx.Response(
                200,
                json={
                    "memory_event_id": str(uuid.uuid4()),
                    "event_type": "explore_capability_clicked",
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
                        "status": "completed",
                        "task_spec": task_spec,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "events": [
                        {"event_type": "exercise_answered"},
                        {"event_type": "exercise_graded"},
                        {"event_type": "mastery_updated"},
                        {
                            "event_type": "explore_capability_recommended",
                            "payload": {"recommendations": [capability_recommendation]},
                        },
                    ],
                    "tool_calls": [
                        {
                            "tool_name": "exercise.grade",
                            "status": "success",
                            "latency_ms": 12,
                        }
                    ],
                    "checkpoint": {
                        "checkpoint_id": checkpoint_id,
                        "episode_id": episode_id,
                        "learner_id": learner_id,
                        "thread_id": f"daily-lesson:{episode_id}",
                        "checkpoint_key": f"{episode_id}:task",
                        "status": "completed",
                        "resume_from": "generate_feedback",
                        "answer_required": False,
                        "prompt_payload": {"prompt": "Choose the greeting."},
                        "state_snapshot": {},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "consumed_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
        if request.method == "GET" and request.url.path == f"/api/runtime/episodes/{episode_id}/verification":
            return httpx.Response(
                200,
                json={
                    "episode_id": episode_id,
                    "task_id": task_spec["task_id"],
                    "status": "passed",
                    "checks": [],
                    "failed_reason": None,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {},
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    async with client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["episode_runtime_knowledge_practice"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.runtime_metrics["episode_count"] == 1
    assert report.runtime_metrics["completed_episode_count"] == 1
    assert report.runtime_metrics["verification_pass_count"] == 1
    assert report.to_dict()["runtime_metrics"]["avg_tool_latency_ms"] == 12


@pytest.mark.asyncio
async def test_daily_lesson_capability_recommendation_simulation_clicks_memory_event():
    learner_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    task_spec = _task_spec(f"task:{target_id}", target_id)
    recommendation = {
        "recommendation_id": "caprec:grammar",
        "capability_id": "grammar-explain",
        "feature_id": "grammar-explain",
        "title": "语法微知识点",
        "reason": "语法错误适合继续补一个微知识点。",
        "priority_score": 0.91,
        "category": "grammar",
        "action": "tool",
        "tool_target": "grammar",
        "route_hint": None,
        "prompt_seed": None,
        "input_payload": {},
        "evidence_refs": [],
        "source": "rule",
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
                    "tasks": [
                        {
                            "task_spec": task_spec,
                            "priority_score": 0.9,
                            "reason": "Practice the next knowledge point.",
                            "evidence_refs": [],
                            "estimated_minutes": 5,
                        }
                    ],
                    "evidence_refs": [],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
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
                    "resume_from": "generate_feedback",
                    "prompt": "Choose the greeting.",
                    "initial_payload": {"options": ["Good morning!", "Other"]},
                    "recommendation_reason": "Mock recommendation",
                },
            )
        if request.method == "POST" and request.url.path == f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer":
            return httpx.Response(
                200,
                json={
                    "feedback": "Grammar needs review.",
                    "grading_result": {"correct": False, "error_type": "grammar_rule_confusion"},
                    "mastery_update": {"new_score": 0.25},
                    "memory_updates": [{"memory_event_id": str(uuid.uuid4())}],
                    "verification_status": "passed",
                    "status": "completed",
                    "checkpoint_status": "completed",
                    "next_recommendation": None,
                    "next_capability_recommendations": [recommendation],
                    "episode_id": episode_id,
                },
            )
        if (
            request.method == "POST"
            and request.url.path
            == f"/api/learners/{learner_id}/explore/capabilities/grammar-explain/events"
        ):
            return httpx.Response(
                200,
                json={
                    "memory_event_id": str(uuid.uuid4()),
                    "event_type": "explore_capability_clicked",
                },
            )
        if request.method == "GET" and request.url.path == f"/api/runtime/episodes/{episode_id}":
            return httpx.Response(
                200,
                json={
                    "episode": {"id": episode_id, "status": "completed"},
                    "events": [
                        {"event_type": "exercise_answered"},
                        {
                            "event_type": "explore_capability_recommended",
                            "payload": {"recommendations": [recommendation]},
                        },
                    ],
                    "tool_calls": [],
                    "checkpoint": {"checkpoint_id": checkpoint_id, "status": "completed"},
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    async with client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["daily_lesson_capability_recommendation"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
    )

    assert report.status == "passed"
    assert report.metrics["memory_write_count"] == 1
