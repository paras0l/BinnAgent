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
        "reading_material": None,
        "reading_material_id": str(uuid.uuid4()),
        "reading_attempt_id": str(uuid.uuid4()),
        "reading_completions": {},
        "reading_sentence_analyses": {},
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
    if method == "POST" and path == f"/api/learners/{learner_id}/reading-workshop/materials":
        return _save_reading_material(request, state)
    if (
        method == "POST"
        and path
        == (
            f"/api/learners/{learner_id}/reading-workshop/materials/"
            f"{state['reading_material_id']}/sentence-analysis"
        )
    ):
        return _analyze_reading_sentence(request, state)
    if (
        method == "POST"
        and path
        == (
            f"/api/learners/{learner_id}/reading-workshop/materials/"
            f"{state['reading_material_id']}/complete"
        )
    ):
        return _complete_reading_material(request, state)
    if method == "GET" and path == f"/api/learners/{learner_id}/dashboard":
        return _reading_dashboard(state)
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


def _save_reading_material(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    body = _json_body(request)
    text = str(body.get("text") or "").strip()
    material = {
        "id": state["reading_material_id"],
        "learner_id": state["learner_id"],
        "title": body.get("title"),
        "text": text,
        "level": body.get("level", "general"),
        "goal": body.get("goal", "mixed"),
        "material_type": body.get("material_type", "passage"),
        "word_count": len(text.split()),
        "sentence_count": 2,
        "source": "reading_workshop",
        "curriculum_node_id": None,
        "generation_context": {},
        "created_at": "2026-07-14T00:00:00+00:00",
        "updated_at": "2026-07-14T00:00:00+00:00",
    }
    state["reading_material"] = material
    return httpx.Response(201, json=material)


def _analyze_reading_sentence(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    material = state.get("reading_material")
    if not isinstance(material, dict):
        return httpx.Response(404, json={"detail": "Reading material not found"})
    body = _json_body(request)
    sentence_id = str(body.get("sentence_id") or "")
    client_attempt_id = str(body.get("client_attempt_id") or "")
    cache_key = f"{sentence_id}:{client_attempt_id}"
    existing = state["reading_sentence_analyses"].get(cache_key)
    if existing:
        return httpx.Response(200, json=existing)
    unable = bool(body.get("unable_to_analyze"))
    response = {
        "material_id": state["reading_material_id"],
        "sentence_id": sentence_id,
        "sentence": "Good readers first identify the writer's main idea.",
        "event_id": f"reading-sentence-analysis:{state['reading_material_id']}:{client_attempt_id}",
        "workflow_stage": "review",
        "outcome": "NO_ATTEMPT" if unable else "SUCCESS",
        "score": 0.0 if unable else 0.9,
        "confidence": 0.94,
        "feedback": "先定位主句谓语，再处理修饰信息。",
        "correct_analysis": {
            "main_structure": "Good readers identify the main idea",
            "clause_layers": [],
            "phrases": [],
            "sentence_meaning": "优秀的读者先确定作者的主旨。",
        },
        "teaching": {
            "required": unable,
            "explanation": "先找主语和谓语。" if unable else "",
            "steps": ["找主语", "找谓语"] if unable else [],
            "checkpoint": "谁做了什么？" if unable else "",
        },
        "can_do_points": [
            {
                "can_do_id": "egp:simulation-reading",
                "knowledge_point_id": state["target_id"],
                "statement": "能识别句子主干与修饰信息。",
                "cefr_level": "A2",
                "category": "句子结构",
                "subcategory": "主干识别",
                "confidence": 0.9,
                "mastery_before": None if unable else 0.4,
                "mastery_after": None if unable else 0.58,
                "evidence_status": "teaching_only" if unable else "applied",
            }
        ],
        "error_patterns": (
            [
                {
                    "tag": "no_attempt",
                    "description": "暂时无法独立开始拆句。",
                    "recommended_drill": "先找主谓，再处理修饰语",
                }
            ]
            if unable
            else []
        ),
        "mastery_updated": not unable,
        "prompt_execution_record_id": None,
    }
    state["reading_sentence_analyses"][cache_key] = response
    return httpx.Response(200, json=response)


def _complete_reading_material(request: httpx.Request, state: dict[str, Any]) -> httpx.Response:
    material = state.get("reading_material")
    if not isinstance(material, dict):
        return httpx.Response(404, json={"detail": "Reading material not found"})

    body = _json_body(request)
    client_attempt_id = str(body.get("client_attempt_id") or "").strip()
    if not 8 <= len(client_attempt_id) <= 100:
        return httpx.Response(422, json={"detail": "Invalid client attempt id"})

    extensive_evidence = body.get("extensive_evidence")
    has_extensive_evidence = (
        isinstance(extensive_evidence, dict)
        and bool(str(extensive_evidence.get("gist") or "").strip())
        and bool(str(extensive_evidence.get("central_sentence") or "").strip())
    )
    analyzed_sentence_ids = body.get("analyzed_sentence_ids")
    normalized_sentence_ids = (
        [str(value).strip() for value in analyzed_sentence_ids]
        if isinstance(analyzed_sentence_ids, list)
        else []
    )
    if len(normalized_sentence_ids) > 500:
        return httpx.Response(
            422,
            json={"detail": "analyzed_sentence_ids must contain at most 500 values"},
        )
    if any(not sentence_id for sentence_id in normalized_sentence_ids):
        return httpx.Response(
            422,
            json={"detail": "analyzed_sentence_ids must not contain blank values"},
        )
    if any(len(sentence_id) > 100 for sentence_id in normalized_sentence_ids):
        return httpx.Response(
            422,
            json={"detail": "analyzed_sentence_ids values must be at most 100 characters"},
        )
    if len(normalized_sentence_ids) != len(set(normalized_sentence_ids)):
        return httpx.Response(
            422,
            json={"detail": "analyzed_sentence_ids must not contain duplicate values"},
        )
    has_intensive_evidence = bool(normalized_sentence_ids)
    goal = material.get("goal")
    if goal in {"extensive", "mixed"} and not has_extensive_evidence:
        return httpx.Response(
            422,
            json={"detail": "Extensive reading completion requires reading evidence"},
        )
    if goal in {"intensive", "mixed"} and not has_intensive_evidence:
        return httpx.Response(
            422,
            json={"detail": "Intensive reading completion requires analyzed sentence ids"},
        )
    allowed_sentence_ids = {
        f"reading-sentence-{index}"
        for index in range(1, int(material.get("sentence_count") or 0) + 1)
    }
    unknown_sentence_ids = [
        sentence_id
        for sentence_id in normalized_sentence_ids
        if sentence_id not in allowed_sentence_ids
    ]
    if unknown_sentence_ids:
        return httpx.Response(
            422,
            json={"detail": "analyzed_sentence_ids must reference sentences in this reading material"},
        )

    existing = state["reading_completions"].get(client_attempt_id)
    if existing is not None:
        return httpx.Response(200, json=existing["response"])

    comprehension_score = body.get("comprehension_score")
    reading_value = int(comprehension_score) if isinstance(comprehension_score, int) else 60
    response = {
        "material_id": state["reading_material_id"],
        "attempt_id": state["reading_attempt_id"],
        "reading_value": reading_value,
        "message": "阅读训练已记录。",
    }
    state["reading_completions"][client_attempt_id] = {
        "response": response,
        "comprehension_score": comprehension_score,
        "reading_value": reading_value,
    }
    return httpx.Response(200, json=response)


def _reading_dashboard(state: dict[str, Any]) -> httpx.Response:
    completions = list(state["reading_completions"].values())
    ability_scores: list[dict[str, Any]] = []
    scored_completions = [
        item
        for item in completions
        if isinstance(item.get("comprehension_score"), (int, float))
    ]
    if scored_completions:
        scores = [
            max(0.0, min(100.0, float(item["comprehension_score"])))
            for item in scored_completions
        ]
        ability_scores.append(
            {
                "label": "阅读",
                "value": round(sum(scores) / len(scores)),
                "evidence_count": len(scored_completions),
            }
        )
    return httpx.Response(
        200,
        json={"profile": {"ability_scores": ability_scores}},
    )


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
