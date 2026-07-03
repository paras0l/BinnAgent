from dataclasses import dataclass
from typing import Any
import uuid

from src.graph.state import LearningGraphState as LearningState
from src.knowledge.exercise_grader import answer_to_text, grade_exercise_answer


@dataclass
class _QuestionLike:
    id: str
    question_type: str
    stem: str
    options: list[str]
    answer: str
    explanation: str
    metadata_: dict[str, Any]
    knowledge_point_id: str | None = None
    curriculum_node_id: str | None = None
    source_id: str | None = None


async def grade_attempt(state: LearningState) -> dict[str, Any]:
    learner_answer = state.get("learner_answer")
    submitted = answer_to_text(learner_answer or "")
    if not submitted:
        return {
            "grade_result": {
                "status": "skipped",
                "correct": False,
                "score": 0.0,
                "error_type": "missing_answer",
                "feedback": "Learner answer is required before grading.",
            },
            "wrong_reason": "missing_answer",
        }

    material = _first_material(state)
    question = _question_from_material(material, state)
    grading = grade_exercise_answer(question, submitted, attempt_index=_attempt_index(state))
    attempt_id = state.get("exercise_attempt_id") or _stable_attempt_id(state, submitted)
    evidence_refs = _evidence_refs(state, material, question, attempt_id)
    knowledge_point_ids = _knowledge_point_ids(state, material, question)
    grade_result = {
        **grading,
        "status": "graded",
        "question_id": question.id,
        "exercise_attempt_id": attempt_id,
        "evidence_refs": evidence_refs,
    }
    return {
        "exercise_attempt_id": attempt_id,
        "grade_result": grade_result,
        "wrong_reason": grading.get("error_type"),
        "knowledge_point_ids": knowledge_point_ids,
        "evidence_refs": evidence_refs,
    }


def _first_material(state: LearningState) -> dict[str, Any]:
    materials = state.get("input_materials") or []
    first = materials[0] if materials and isinstance(materials[0], dict) else {}
    return dict(first)


def _question_from_material(material: dict[str, Any], state: LearningState) -> _QuestionLike:
    selected_task = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    metadata = selected_task.get("metadata") if isinstance(selected_task.get("metadata"), dict) else {}
    target = selected_task.get("target") if isinstance(selected_task.get("target"), dict) else {}
    question_metadata = metadata.get("question") if isinstance(metadata.get("question"), dict) else {}
    answer = (
        material.get("answer")
        or material.get("correct_answer")
        or question_metadata.get("answer")
        or _first_option(material)
    )
    question_id = material.get("question_id") or question_metadata.get("question_id") or material.get("task_id")
    target_id = material.get("target_id") or target.get("target_id")
    target_type = material.get("target_type") or target.get("target_type")
    knowledge_point_id = (
        material.get("knowledge_point_id")
        or question_metadata.get("knowledge_point_id")
        or (target_id if target_type == "knowledge_point" else None)
    )
    return _QuestionLike(
        id=str(question_id or state.get("current_task_id") or "daily:question"),
        question_type=str(material.get("question_type") or question_metadata.get("question_type") or "open"),
        stem=str(material.get("stem") or material.get("prompt") or ""),
        options=[str(item) for item in (material.get("options") or [])],
        answer=str(answer or ""),
        explanation=str(material.get("explanation") or question_metadata.get("explanation") or ""),
        metadata_=dict(material.get("metadata") or question_metadata.get("metadata") or {}),
        knowledge_point_id=str(knowledge_point_id) if knowledge_point_id else None,
        curriculum_node_id=str(material.get("curriculum_node_id") or ""),
        source_id=str(material.get("source_id") or ""),
    )


def _first_option(material: dict[str, Any]) -> str:
    options = material.get("options") or []
    if isinstance(options, list) and options:
        return str(options[0])
    return ""


def _attempt_index(state: LearningState) -> int:
    metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    try:
        return int(metadata.get("attempt_index") or 0)
    except (TypeError, ValueError):
        return 0


def _stable_attempt_id(state: LearningState, submitted: str) -> str:
    seed = "|".join(
        [
            str(state.get("thread_id") or ""),
            str(state.get("episode_id") or ""),
            str(state.get("current_task_id") or ""),
            submitted,
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _knowledge_point_ids(
    state: LearningState,
    material: dict[str, Any],
    question: _QuestionLike,
) -> list[str]:
    existing = [str(item) for item in (state.get("knowledge_point_ids") or []) if item]
    if question.knowledge_point_id:
        existing.append(question.knowledge_point_id)
    target = state.get("selected_task") if isinstance(state.get("selected_task"), dict) else {}
    target_payload = target.get("target") if isinstance(target.get("target"), dict) else {}
    if target_payload.get("target_type") == "knowledge_point" and target_payload.get("target_id"):
        existing.append(str(target_payload["target_id"]))
    if material.get("knowledge_point_id"):
        existing.append(str(material["knowledge_point_id"]))
    return list(dict.fromkeys(existing))


def _evidence_refs(
    state: LearningState,
    material: dict[str, Any],
    question: _QuestionLike,
    attempt_id: str,
) -> list[dict[str, Any]]:
    refs = list(state.get("evidence_refs") or [])
    refs.append(
        {
            "evidence_type": "exercise_attempt",
            "evidence_id": attempt_id,
            "reason": "daily lesson answer graded",
            "used_by": "grade_attempt",
        }
    )
    question_id = question.id or material.get("question_id")
    if question_id:
        refs.append(
            {
                "evidence_type": "exercise_question",
                "evidence_id": str(question_id),
                "reason": "graded question",
                "used_by": "grade_attempt",
            }
        )
    for knowledge_point_id in _knowledge_point_ids(state, material, question):
        refs.append(
            {
                "evidence_type": "knowledge_point",
                "evidence_id": knowledge_point_id,
                "reason": "daily lesson target",
                "used_by": "grade_attempt",
            }
        )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        key = (str(ref.get("evidence_type") or ref.get("type")), str(ref.get("evidence_id") or ref.get("id")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped
