from datetime import datetime, timezone
from typing import Any

from src.graph.state import LearningGraphState as LearningState


async def verify_episode(state: LearningState) -> dict:
    """Produce a graph-level verification report from required policy checks."""
    required_checks = _required_checks(state)
    checks = [_run_check(name, state) for name in required_checks]
    failed = [check for check in checks if not check["passed"]]
    status = "passed" if not failed else "failed"
    return {
        "feedback_ready": bool(state.get("agent_feedback")),
        "verification_report": {
            "episode_id": state.get("episode_id"),
            "status": status,
            "checks": checks,
            "failed_reason": "; ".join(check["message"] or check["name"] for check in failed) or None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "daily_lesson_graph",
            "required_checks": required_checks,
        },
    }


def _required_checks(state: LearningState) -> list[str]:
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    policy = (
        selected_task.get("verification_policy")
        if isinstance(selected_task.get("verification_policy"), dict)
        else {}
    )
    checks = [str(item) for item in (policy.get("required_checks") or []) if str(item).strip()]
    if checks:
        return checks
    return ["answer_received", "feedback_ready", "review_items_prepared"]


def _run_check(name: str, state: LearningState) -> dict[str, Any]:
    normalized = _normalize(name)
    passed, expected, actual, source_node, evidence_refs = _check(normalized, state)
    return {
        "name": normalized,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "source_node": source_node,
        "evidence_refs": evidence_refs,
        "message": None if passed else f"Missing or invalid {normalized}",
    }


def _normalize(name: str) -> str:
    aliases = {
        "answer_received": "learner_answer_received",
        "feedback_ready": "feedback_ready",
        "review_items_prepared": "review_scheduled",
        "grading_result_exists": "exercise_graded",
        "exercise_attempt_saved": "exercise_attempt_created",
        "memory_written": "memory_event_written",
    }
    normalized = name.strip()
    return aliases.get(normalized, normalized)


def _check(name: str, state: LearningState) -> tuple[bool, Any, Any, str, list[dict[str, Any]]]:
    evidence_refs = state.get("evidence_refs") or []
    if name == "task_prepared":
        actual = {
            "current_task_id": state.get("current_task_id"),
            "input_material_count": len(state.get("input_materials") or []),
        }
        return bool(actual["current_task_id"] and actual["input_material_count"]), "task id and materials", actual, "run_learning_task", evidence_refs
    if name == "learner_answer_received":
        actual = state.get("learner_answer")
        return bool(actual), "learner_answer", actual, "wait_for_answer", evidence_refs
    if name == "exercise_attempt_created":
        actual = state.get("exercise_attempt_id")
        return bool(actual), "exercise_attempt_id", actual, "grade_attempt", evidence_refs
    if name == "exercise_graded":
        actual = state.get("grade_result")
        return bool(actual and actual.get("status") == "graded"), "grade_result.status=graded", actual, "grade_attempt", evidence_refs
    if name == "mastery_updated":
        actual = state.get("mastery_update")
        return bool(actual and actual.get("status") != "skipped"), "mastery_update", actual, "update_mastery", evidence_refs
    if name == "memory_event_written":
        actual = state.get("memory_write_result") or {}
        passed = actual.get("status") in {"written", "prepared"} or bool(state.get("memory_candidates"))
        return passed, "memory_write_result", actual, "update_memory", evidence_refs
    if name == "review_scheduled":
        actual = state.get("review_schedule_result") or {}
        passed = actual.get("status") == "scheduled" or bool(state.get("review_items"))
        return passed, "review_schedule_result.status=scheduled", actual, "schedule_review", evidence_refs
    if name == "next_action_recommended":
        actual = state.get("recommendation_result") or state.get("recommended_action")
        return bool(actual), "recommendation_result", actual, "recommend_learning_action", evidence_refs
    if name == "feedback_ready":
        actual = state.get("agent_feedback")
        return bool(actual), "agent_feedback", actual, "generate_feedback", evidence_refs
    actual = None
    return False, "supported verification check", actual, "verify_episode", evidence_refs
