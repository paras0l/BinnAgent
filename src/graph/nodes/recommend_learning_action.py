from typing import Any

from src.graph.state import LearningGraphState as LearningState


async def recommend_learning_action(state: LearningState) -> dict[str, Any]:
    grade_result = state.get("grade_result") or {}
    mastery_update = state.get("mastery_update") or {}
    wrong_reason = state.get("wrong_reason") or grade_result.get("error_type")
    evidence_refs = state.get("evidence_refs") or mastery_update.get("evidence_refs") or []
    correct = bool(grade_result.get("correct"))
    new_score = _score(mastery_update.get("new_score"))

    if correct and new_score >= 0.75:
        action_type = "advance"
        reason = "Answer was correct and mastery is high enough to move forward."
        priority = "low"
    elif correct:
        action_type = "review_later"
        reason = "Answer was correct; schedule a light review to stabilize recall."
        priority = "medium"
    elif wrong_reason and str(wrong_reason).startswith("grammar"):
        action_type = "repair_grammar"
        reason = "The error pattern points to a grammar micro-skill."
        priority = "high"
    else:
        action_type = "retry_with_hint"
        reason = "The answer was not correct; retry with a targeted hint before advancing."
        priority = "high"

    recommended_action = {
        "type": action_type,
        "priority": priority,
        "reason": reason,
        "target_type": mastery_update.get("target_type"),
        "target_id": mastery_update.get("target_id"),
        "wrong_reason": wrong_reason,
    }
    recommendation_result = {
        "status": "recommended",
        "recommended_action": recommended_action,
        "evidence_refs": evidence_refs,
    }
    return {
        "recommended_action": recommended_action,
        "recommendation_result": recommendation_result,
    }


def _score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
