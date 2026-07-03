from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from src.simulation.scenario import SimulationScenario


def build_contract_transport(scenario: SimulationScenario) -> httpx.MockTransport:
    state: dict[str, Any] = {
        "scenario_id": scenario.id,
        "learner_id": str(uuid.uuid4()),
        "episode_id": str(uuid.uuid4()),
        "checkpoint_id": str(uuid.uuid4()),
        "attempt_id": str(uuid.uuid4()),
        "target_id": str(uuid.uuid4()),
        "vocabulary_items": [],
        "answered": False,
        "verification_failed": scenario.id == "daily_lesson_verification_failure_blocks_completed_status",
        "capability_clicked": False,
        "last_vocabulary_mode": "new",
    }
    return httpx.MockTransport(lambda request: _handle(request, state))


async def contract_graph_invoker(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "input_materials": [{"type": "vocabulary", "word": "morning"}],
        "agent_feedback": {"message": "Practice scheduled."},
        "memory_candidates": [{"skill": "vocabulary", "evidence": "simulation"}],
        "review_items": [{"type": "word", "word": "morning"}],
        "summary": "Daily lesson completed.",
    }


def _handle(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    path = request.url.path
    method = request.method
    learner_id = state["learner_id"]
    episode_id = state["episode_id"]

    if method == "POST" and path == "/api/learners":
        return httpx.Response(201, json={"id": learner_id, "nickname": "sim"})
    if method == "POST" and path == "/api/chat/send":
        return _chat_response(request, state)
    if method == "GET" and path == f"/api/learners/{learner_id}/memory/summary":
        return httpx.Response(
            200,
            json={"learner": {"id": learner_id}, "vocabulary": {"total": len(state["vocabulary_items"])}},
        )
    if method == "GET" and path == f"/api/learners/{learner_id}/vocabulary":
        return httpx.Response(200, json=state["vocabulary_items"])
    if method == "POST" and path == f"/api/learners/{learner_id}/vocabulary/add":
        return _add_vocabulary(request, state)
    if path.startswith(f"/api/learners/{learner_id}/vocabulary/sessions"):
        return _vocabulary_session_response(request, state)
    if method == "GET" and path.startswith(f"/api/learners/{learner_id}/vocabulary/"):
        return _vocabulary_detail_response(path, state)
    if method == "GET" and path == "/api/recommendations/daily-plan":
        return httpx.Response(200, json=_daily_plan(state))
    if method == "POST" and path == f"/api/learners/{learner_id}/daily-lessons/start":
        return httpx.Response(200, json=_daily_lesson_start(state))
    if method == "POST" and path == f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer":
        return _daily_lesson_answer(request, state)
    if method == "GET" and path == f"/api/runtime/episodes/{episode_id}":
        return httpx.Response(200, json=_episode_trace(state))
    if method == "GET" and path == f"/api/runtime/episodes/{episode_id}/verification":
        return httpx.Response(200, json=_verification_report(state))
    if method == "POST" and path.endswith("/explore/capabilities/grammar-explain/events"):
        state["capability_clicked"] = True
        return httpx.Response(
            200,
            json={
                "event_type": "explore_capability_clicked",
                "capability_id": "grammar-explain",
                "episode_id": episode_id,
            },
        )
    if method == "POST" and path == f"/api/learners/{learner_id}/exercises/generate":
        return httpx.Response(200, json=[_generated_exercise()])
    return httpx.Response(404, json={"detail": f"contract mock route not found: {method} {path}"})


def _chat_response(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    body = _json_body(request)
    skill_id = body.get("skill_id")
    skill_events = []
    if skill_id == "vocabulary_deposit":
        _seed_vocabulary(state, ["significant", "sustainable", "evidence"])
        skill_events = [{"status": "completed", "saved_count": 3, "skipped_count": 0}]
    return httpx.Response(
        200,
        json={
            "reply": "Let's practice vocabulary.",
            "response": "Let's practice vocabulary.",
            "thread_id": str(uuid.uuid4()),
            "message_id": str(uuid.uuid4()),
            "skill_id": skill_id,
            "skill_name": "Vocabulary Deposit" if skill_id else None,
            "skill_events": skill_events,
        },
    )


def _add_vocabulary(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    body = _json_body(request)
    word = str(body.get("word") or f"word-{len(state['vocabulary_items'])}")
    item = {
        "id": str(uuid.uuid4()),
        "word": word,
        "status": "learning",
        "confidence": 0.0,
        "mastery": {"recognition": 0.1, "spelling": 0.1},
        "mistakes": [],
    }
    state["vocabulary_items"].append(item)
    return httpx.Response(200, json=item)


def _vocabulary_session_response(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path.endswith("/sessions"):
        mode = _json_body(request).get("mode", "new")
        state["last_vocabulary_mode"] = mode
        state["last_session_id"] = str(uuid.uuid4())
        return httpx.Response(
            201,
            json={"session_id": state["last_session_id"], "mode": mode, "total": 1, "current_index": 0},
        )
    if request.method == "GET" and path.endswith("/next"):
        items = state["vocabulary_items"] or []
        item = items[1] if state.get("last_vocabulary_mode") == "spelling" and len(items) > 1 else items[0]
        return httpx.Response(
            200,
            json={
                "completed": False,
                "vocabulary_item_id": item["id"],
                "display_word": item["word"],
                "prompt_mode": "meaning",
            },
        )
    if request.method == "POST" and path.endswith("/attempts"):
        spelling = state.get("last_vocabulary_mode") == "spelling"
        return httpx.Response(
            200,
            json={
                "attempt_id": str(uuid.uuid4()),
                "result": "incorrect" if spelling else "correct",
                "correct_answer": "telephone" if spelling else "morning",
                "error_type": "missing" if spelling else None,
            },
        )
    if request.method == "POST" and path.endswith("/advance"):
        return httpx.Response(200, json={"status": "completed", "completed": 1, "correct": 1})
    if request.method == "GET" and path.endswith("/summary"):
        return httpx.Response(200, json={"status": "completed", "completed": 1, "correct": 1})
    if request.method == "GET":
        item_id = path.rstrip("/").split("/")[-1]
        item = next((item for item in state["vocabulary_items"] if item["id"] == item_id), None)
        if item:
            spelling = state.get("last_vocabulary_mode") == "spelling"
            return httpx.Response(
                200,
                json={
                    **item,
                    "mastery": {"recognition": 0.2, "spelling": 0.0 if spelling else 0.1},
                    "mistakes": [{"mistake_type": "missing", "active": True}] if spelling else [],
                },
            )
    return httpx.Response(404, json={"detail": "vocabulary route not found"})


def _vocabulary_detail_response(path: str, state: dict[str, Any]) -> httpx.Response:
    item_id = path.rstrip("/").split("/")[-1]
    item = next((item for item in state["vocabulary_items"] if item["id"] == item_id), None)
    if item is None:
        return httpx.Response(404, json={"detail": "Vocabulary item not found"})
    spelling = state.get("last_vocabulary_mode") == "spelling"
    return httpx.Response(
        200,
        json={
            **item,
            "mastery": {"recognition": 0.2, "spelling": 0.0 if spelling else 0.1},
            "mistakes": [{"mistake_type": "missing", "active": True}] if spelling else [],
        },
    )


def _daily_plan(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": "plan:simulation",
        "learner_id": state["learner_id"],
        "mode": "textbook_guided",
        "reason": "Mock recommendation",
        "confidence": 0.9,
        "tasks": [{"task_spec": _task_spec(state), "priority_score": 0.9, "reason": "Practice"}],
        "evidence_refs": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _daily_lesson_start(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": state["episode_id"],
        "task_spec": _task_spec(state),
        "status": "waiting_user",
        "answer_required": True,
        "checkpoint_id": state["checkpoint_id"],
        "checkpoint_status": "waiting_user",
        "resume_from": "grade_attempt",
        "thread_id": f"daily-lesson:{state['episode_id']}",
        "prompt": "Choose the greeting.",
        "prompt_payload": {"prompt": "Choose the greeting."},
        "required_input_schema": {"required": ["answer"]},
        "initial_payload": {"options": ["Good morning!", "Other"]},
        "recommendation_reason": "Mock recommendation",
    }


def _daily_lesson_answer(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    body = _json_body(request)
    answer = str(body.get("answer") or "")
    state["answered"] = True
    state["last_answer"] = answer
    wrong = "I good" in answer
    verification_failed = bool(state["verification_failed"])
    status = "verification_failed" if verification_failed else "completed"
    recommendations = [_grammar_recommendation()] if wrong else []
    return httpx.Response(
        200,
        json={
            "feedback": "Review word order." if wrong else "Correct.",
            "grading_result": {"correct": not wrong, "score": 0.0 if wrong else 1.0},
            "mastery_update": {"new_score": 0.3, "mastery_delta": -0.2 if wrong else 0.2},
            "memory_updates": []
            if verification_failed
            else [{"memory_event_id": str(uuid.uuid4()), "evidence_refs": ["sim"]}],
            "review_schedule_result": {"status": "scheduled"},
            "verification_status": "failed" if verification_failed else "passed",
            "status": status,
            "checkpoint_status": "completed",
            "recommendation_result": {"status": "recommended"},
            "exercise_attempt_id": state["attempt_id"],
            "next_capability_recommendations": recommendations,
            "episode_id": state["episode_id"],
        },
    )


def _episode_trace(state: dict[str, Any]) -> dict[str, Any]:
    if not state["answered"]:
        return {
            "episode": {"id": state["episode_id"], "status": "waiting_user", "task_spec": _task_spec(state)},
            "events": [
                {"event_type": "episode_started"},
                {"event_type": "task_prepared"},
                {"event_type": "graph_interrupted"},
            ],
            "tool_calls": [],
            "checkpoint": {"checkpoint_id": state["checkpoint_id"], "status": "waiting_user"},
        }
    status = "verification_failed" if state["verification_failed"] else "completed"
    events = [
        {"event_type": "graph_interrupted"},
        {"event_type": "graph_resumed"},
        {"event_type": "learner_answer_received"},
        {"event_type": "exercise_attempt_created"},
        {"event_type": "exercise_graded"},
        {"event_type": "mastery_updated"},
        {"event_type": "memory_written"},
        {"event_type": "review_scheduled"},
        {"event_type": "next_action_recommended"},
        {"event_type": "verification_report_generated"},
        {"event_type": "episode_completed"},
    ]
    if "I good" in str(state.get("last_answer")):
        events.append({"event_type": "explore_capability_recommended"})
    return {
        "episode": {"id": state["episode_id"], "status": status, "task_spec": _task_spec(state)},
        "events": events,
        "tool_calls": [
            {"tool_name": "exercise.grade", "status": "success", "latency_ms": 15},
            {"tool_name": "mastery.update", "status": "success", "latency_ms": 8},
            {"tool_name": "memory.write", "status": "success", "latency_ms": 10},
            {"tool_name": "verification.verify_episode", "status": "success", "latency_ms": 5},
        ],
        "checkpoint": {"checkpoint_id": state["checkpoint_id"], "status": "completed"},
        "verification_report": _verification_report(state),
        "prompt_executions": [],
    }


def _verification_report(state: dict[str, Any]) -> dict[str, Any]:
    failed = bool(state["verification_failed"])
    return {
        "status": "failed" if failed else "passed",
        "checks": [
            {"name": "exercise_graded", "status": "passed", "passed": True},
            {"name": "mastery_updated", "status": "passed", "passed": True},
        ],
    }


def _task_spec(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": f"task:{state['target_id']}",
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "objective": "Practice greeting",
        "target": {"target_type": "knowledge_point", "target_id": state["target_id"]},
        "difficulty": "easy",
        "required_inputs": [],
        "expected_output": {},
        "allowed_tools": ["exercise.grade", "mastery.update", "memory.write"],
        "success_criteria": {"min_accuracy": 1.0, "requires_explanation": True},
        "verification_policy": {"required_checks": ["exercise_graded", "mastery_updated"], "require_evidence": True},
        "metadata": {},
    }


def _grammar_recommendation() -> dict[str, Any]:
    return {
        "capability_id": "grammar-explain",
        "recommendation_id": "caprec:simulation",
        "reason": "Word order weakness detected.",
        "priority_score": 0.9,
        "evidence_refs": [],
    }


def _generated_exercise() -> dict[str, Any]:
    return {
        "id": "generated:simulation",
        "skill": "vocabulary",
        "type": "single_choice",
        "prompt": "Which expression is a morning greeting?",
        "options": ["Good morning!", "Good night!", "Thank you."],
        "correctAnswer": "Good morning!",
        "answer": "Good morning!",
        "explanation": "Good morning is used in the morning.",
        "difficulty": "easy",
    }


def _seed_vocabulary(state: dict[str, Any], words: list[str]) -> None:
    for word in words:
        if any(item["word"] == word for item in state["vocabulary_items"]):
            continue
        state["vocabulary_items"].append(
            {
                "id": str(uuid.uuid4()),
                "word": word,
                "status": "learning",
                "confidence": 0.0,
            }
        )


def _json_body(request: httpx.Request) -> dict[str, Any]:
    try:
        value = json.loads(request.content.decode("utf-8"))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
