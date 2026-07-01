from typing import Any, Literal

from src.models.knowledge import ExerciseQuestion

ExerciseItemSkill = Literal["grammar", "vocabulary", "reading"]
ExerciseItemType = Literal["single_choice", "fill_blank"]


def exercise_question_to_item(
    question: ExerciseQuestion,
    *,
    target_label: str | None = None,
) -> dict[str, Any]:
    metadata = dict(question.metadata_ or {})
    rubric = metadata.get("rubric") if isinstance(metadata.get("rubric"), dict) else {}

    metadata.update(
        {
            "knowledge_point_id": str(question.knowledge_point_id)
            if question.knowledge_point_id
            else None,
            "source_id": str(question.source_id),
            "question_type": question.question_type,
        }
    )

    return {
        "id": str(question.id),
        "target": {
            "type": "curriculum_node",
            "id": str(question.curriculum_node_id),
            "label": target_label or "课程知识库练习",
        },
        "skill": infer_skill_from_question(question),
        "type": map_question_type(question.question_type),
        "prompt": question.stem,
        "options": question.options or [],
        "correctAnswer": question.answer,
        "acceptedAnswers": _accepted_answers(rubric),
        "explanation": question.explanation,
        "difficulty": question.difficulty,
        "source": {
            "type": "curriculum",
            "name": "knowledge_base",
            "refId": str(question.id),
        },
        "metadata": metadata,
    }


def infer_skill_from_question(question: ExerciseQuestion) -> ExerciseItemSkill:
    metadata = question.metadata_ or {}
    skill = metadata.get("skill")
    if skill in ("grammar", "vocabulary", "reading"):
        return skill
    if question.question_type == "error_fix":
        return "grammar"
    if question.question_type in ("choice_context", "dialogue_complete", "fill_blank"):
        return "vocabulary"
    return "reading"


def map_question_type(question_type: str) -> ExerciseItemType:
    if question_type in ("choice_context", "multiple_choice"):
        return "single_choice"
    return "fill_blank"


def _accepted_answers(rubric: dict[str, Any]) -> list[str]:
    accepted_answers = rubric.get("acceptable_answers")
    if not isinstance(accepted_answers, list):
        return []
    return [str(answer) for answer in accepted_answers if str(answer).strip()]
