from typing import Any

from src.graph.state import LearningGraphState as LearningState

ANSWER_REQUIRED_TASK_TYPES = {
    "practice_knowledge_point",
    "learn_knowledge_point",
    "repair_weakness",
    "review_due_item",
}

async def run_learning_task(state: LearningState) -> dict:
    """Execute the learning task based on active_skill.

    For reading: fetch a question from the question bank.
    For writing: provide a writing prompt.
    For vocabulary: provide a vocabulary list.
    """
    selected_task = _task_dict(state.get("selected_task"))
    if selected_task:
        return _run_selected_task(selected_task, state)

    active_skill = state.get("active_skill", "reading")
    target_exam = state.get("target_exam", "CET6")

    if active_skill == "reading":
        from src.tools.question_bank import question_bank

        exam_map = {"CET4": "CET-4", "CET6": "CET-6"}
        exam = exam_map.get(target_exam, "CET-6")
        questions = question_bank.get_questions(
            exam_type=exam, section="reading comprehension", limit=1
        )
        materials = []
        for q in questions:
            materials.append(
                {
                    "type": "reading_question",
                    "material_type": "reading_question",
                    "question_id": q.question_id,
                    "task_id": q.question_id,
                    "passage": q.passage or "",
                    "stem": q.stem,
                    "prompt": q.stem,
                    "options": q.options,
                    "target_type": "question_bank",
                    "target_id": q.question_id,
                }
            )
        return _answer_required_update(
            materials,
            current_task_id=materials[0]["task_id"] if materials else "reading:practice",
            checkpoint_status=state.get("checkpoint_status"),
        )

    elif active_skill == "writing":
        material = {
            "type": "writing_prompt",
            "material_type": "writing_prompt",
            "task_id": "writing:essay",
            "content": "Write an essay on the importance of environmental protection.",
            "stem": "Write an essay on the importance of environmental protection.",
            "prompt": "Write an essay on the importance of environmental protection.",
            "options": [],
            "criteria": ["structure", "vocabulary", "grammar"],
            "target_type": "writing",
            "target_id": "essay",
        }
        return _answer_required_update(
            [material],
            current_task_id=material["task_id"],
            checkpoint_status=state.get("checkpoint_status"),
        )

    elif active_skill == "vocabulary":
        material = {
            "type": "vocabulary_list",
            "material_type": "vocabulary_list",
            "task_id": "vocabulary:daily",
            "stem": "选择一个词并写出你能想到的例句。",
            "prompt": "选择一个词并写出你能想到的例句。",
            "options": ["sustainable", "significant"],
            "words": [
                {"word": "sustainable", "definition": "able to be maintained over time"},
                {"word": "significant", "definition": "sufficiently great or important"},
            ],
            "target_type": "vocabulary",
            "target_id": "daily",
        }
        return _answer_required_update(
            [material],
            current_task_id=material["task_id"],
            checkpoint_status=state.get("checkpoint_status"),
        )

    return {"input_materials": []}


def _run_selected_task(selected_task: dict[str, Any], state: LearningState) -> dict[str, Any]:
    task_id = str(selected_task.get("task_id") or state.get("current_task_id") or "daily:task")
    task_type = str(selected_task.get("task_type") or "")
    target = selected_task.get("target") if isinstance(selected_task.get("target"), dict) else {}
    metadata = selected_task.get("metadata") if isinstance(selected_task.get("metadata"), dict) else {}
    expected_output = (
        selected_task.get("expected_output")
        if isinstance(selected_task.get("expected_output"), dict)
        else {}
    )
    question = (
        metadata.get("question")
        if isinstance(metadata.get("question"), dict)
        else expected_output.get("question")
        if isinstance(expected_output.get("question"), dict)
        else None
    )

    if question:
        material = {
            "type": "knowledge_question",
            "material_type": "exercise_question",
            "question_id": question.get("question_id") or question.get("id"),
            "task_id": task_id,
            "stem": question.get("stem") or selected_task.get("objective"),
            "prompt": question.get("stem") or selected_task.get("objective"),
            "options": question.get("options") or [],
            "question_type": question.get("question_type"),
            "difficulty": question.get("difficulty"),
            "target_type": target.get("target_type"),
            "target_id": target.get("target_id"),
        }
    else:
        material = {
            "type": "task_prompt",
            "material_type": "task_prompt",
            "task_id": task_id,
            "stem": selected_task.get("objective") or "完成这道学习任务。",
            "prompt": selected_task.get("objective") or "完成这道学习任务。",
            "options": [],
            "target_type": target.get("target_type"),
            "target_id": target.get("target_id"),
        }

    answer_required = task_type in ANSWER_REQUIRED_TASK_TYPES or bool(
        selected_task.get("required_inputs")
    )
    if not answer_required:
        return {
            "input_materials": [material],
            "answer_required": False,
            "current_task_id": task_id,
        }

    return _answer_required_update(
        [material],
        current_task_id=task_id,
        checkpoint_status=state.get("checkpoint_status"),
    )


def _answer_required_update(
    materials: list[dict[str, Any]],
    *,
    current_task_id: str,
    checkpoint_status: str | None,
) -> dict[str, Any]:
    return {
        "input_materials": materials,
        "answer_required": True,
        "checkpoint_status": checkpoint_status or "waiting_user",
        "resume_from": "generate_feedback",
        "current_task_id": current_task_id,
    }


def _task_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}
