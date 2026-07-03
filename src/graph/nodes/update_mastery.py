from datetime import datetime, timedelta, timezone
from typing import Any

from src.graph.state import LearningGraphState as LearningState


async def update_mastery(state: LearningState) -> dict[str, Any]:
    grade_result = state.get("grade_result") or {}
    if grade_result.get("status") == "skipped":
        return {
            "mastery_update": {
                "status": "skipped",
                "reason": grade_result.get("error_type") or "missing_grade",
            }
        }

    target = _target(state)
    if not target["target_id"]:
        return {
            "mastery_update": {
                "status": "skipped",
                "reason": "missing_target",
                "evidence_refs": state.get("evidence_refs") or [],
            }
        }

    correct = bool(grade_result.get("correct"))
    score = _clamp(grade_result.get("score") or 0.0)
    previous_score = _previous_score(state)
    delta = (0.18 + score * 0.04) if correct else -0.12
    new_score = _clamp(previous_score + delta)
    now = datetime.now(timezone.utc)
    next_review_at = _next_review_at(now, correct, new_score)
    mastery_update = {
        "learner_id": str(state.get("learner_id") or state.get("user_id") or ""),
        "target_type": target["target_type"],
        "target_id": target["target_id"],
        "previous_score": previous_score,
        "new_score": new_score,
        "previous_confidence": previous_score,
        "new_confidence": min(1.0, max(previous_score, new_score) + 0.12),
        "mastery_delta": new_score - previous_score,
        "weakness_tags": [] if correct else [str(grade_result.get("error_type") or "needs_review")],
        "forgetting_risk": max(0.0, 1.0 - new_score),
        "next_review_at": next_review_at.isoformat(),
        "status": "learning" if correct else "reviewing",
        "evidence_refs": state.get("evidence_refs") or grade_result.get("evidence_refs") or [],
        "metadata": {
            "source": "daily_lesson_graph",
            "engine": "rule_fallback",
            "grade_score": score,
        },
    }
    return {"mastery_update": mastery_update}


def _target(state: LearningState) -> dict[str, str | None]:
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    target = selected_task.get("target") if isinstance(selected_task.get("target"), dict) else {}
    materials = state.get("input_materials") or []
    material = materials[0] if materials and isinstance(materials[0], dict) else {}
    knowledge_point_ids = state.get("knowledge_point_ids") or []
    target_type = str(target.get("target_type") or material.get("target_type") or "knowledge_point")
    target_id = (
        target.get("target_id")
        or material.get("target_id")
        or (knowledge_point_ids[0] if knowledge_point_ids else None)
    )
    return {
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
    }


def _previous_score(state: LearningState) -> float:
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    metadata = selected_task.get("metadata") if isinstance(selected_task.get("metadata"), dict) else {}
    for key in ("mastery_score", "previous_score"):
        if key in metadata:
            return _clamp(metadata.get(key))
    return 0.3


def _next_review_at(now: datetime, correct: bool, score: float) -> datetime:
    if not correct:
        return now + timedelta(days=1)
    if score >= 0.8:
        return now + timedelta(days=7)
    return now + timedelta(days=4)


def _clamp(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return min(1.0, max(0.0, numeric))
