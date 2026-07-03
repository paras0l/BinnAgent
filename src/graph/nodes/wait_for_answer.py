from typing import Any

from src.graph.state import LearningGraphState as LearningState


async def wait_for_answer(state: LearningState) -> dict[str, Any]:
    """Prepare a learner prompt and pause the graph until an answer exists."""
    current_task_id = _current_task_id(state)
    prompt_payload = _prompt_payload(state, current_task_id)
    required_input_schema = _required_input_schema(state)
    learner_answer = state.get("learner_answer")
    answer_required = bool(state.get("answer_required", True))

    update: dict[str, Any] = {
        "answer_required": answer_required,
        "current_task_id": current_task_id,
        "prompt_payload": prompt_payload,
        "required_input_schema": required_input_schema,
        "resume_from": "grade_attempt",
    }
    if not answer_required:
        update["checkpoint_status"] = state.get("checkpoint_status")
        return update
    if not _has_answer(learner_answer):
        update["checkpoint_status"] = "waiting_user"
        return update

    update["checkpoint_status"] = state.get("checkpoint_status") or "resumed"
    return update


def _current_task_id(state: LearningState) -> str:
    if state.get("current_task_id"):
        return str(state["current_task_id"])
    materials = state.get("input_materials") or []
    first = materials[0] if materials and isinstance(materials[0], dict) else {}
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    return str(first.get("task_id") or selected_task.get("task_id") or "daily:task")


def _prompt_payload(state: LearningState, current_task_id: str) -> dict[str, Any]:
    materials = state.get("input_materials") or []
    first = materials[0] if materials and isinstance(materials[0], dict) else {}
    prompt = (
        first.get("prompt")
        or first.get("stem")
        or first.get("content")
        or "请完成这道学习任务。"
    )
    return {
        "task_id": current_task_id,
        "prompt": str(prompt),
        "input_materials": materials,
    }


def _required_input_schema(state: LearningState) -> dict[str, Any]:
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    required_inputs = selected_task.get("required_inputs") or ["answer"]
    required = [str(item) for item in required_inputs if str(item).strip()] or ["answer"]
    return {
        "type": "object",
        "required": required,
        "properties": {
            "answer": {
                "type": ["string", "object"],
                "description": "Learner answer for the prepared daily lesson task.",
            }
        },
    }


def _has_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        for key in ("answer", "value", "items", "pairs"):
            if key in value and value[key]:
                return True
        return bool(value)
    return True
