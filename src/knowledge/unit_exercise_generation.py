from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import ExerciseQuestion, KnowledgePoint, LearnerKnowledgeState
from src.prompts import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter

UNIT_GENERATOR_VERSION = "unit-exercise-llm-v1"
DEFAULT_POOL_SIZE = 16
MIN_PUBLISHABLE_QUESTIONS = 8
MAX_GENERATION_POINTS = 14

_ACTIVE_TYPES = {"fill_blank", "grammar_fill_blank", "dialogue_complete", "error_fix"}
_QUESTION_TYPES = {
    "choice_context",
    "fill_blank",
    "grammar_fill_blank",
    "dialogue_complete",
    "error_fix",
}
_FORBIDDEN_STEM_MARKERS = ("目标：", "目标:", "使用「", "相关表达")


class UnitExerciseGenerationUnavailableError(RuntimeError):
    """Raised when no reviewed or curated unit exercises can be served."""


def select_generation_points(
    points: list[KnowledgePoint],
    *,
    limit: int = MAX_GENERATION_POINTS,
) -> list[KnowledgePoint]:
    """Prefer teachable unit targets over whichever rows happened to be inserted first."""
    quotas = {
        "sentence_pattern": 3,
        "grammar": 3,
        "phrase": 3,
        "vocabulary": 4,
        "pronunciation": 1,
    }
    selected: list[KnowledgePoint] = []
    selected_ids: set[uuid.UUID] = set()
    for point_type, quota in quotas.items():
        for point in (item for item in points if item.type == point_type):
            if sum(item.type == point_type for item in selected) >= quota:
                break
            selected.append(point)
            selected_ids.add(point.id)
            if len(selected) >= limit:
                return selected
    for point in points:
        if len(selected) >= limit:
            break
        if point.id not in selected_ids and point.type != "text_note":
            selected.append(point)
            selected_ids.add(point.id)
    return selected


def build_coverage_plan(
    points: list[KnowledgePoint],
    *,
    candidate_count: int = DEFAULT_POOL_SIZE,
) -> list[dict[str, Any]]:
    if not points:
        return []

    levels = [
        "production",
        "transfer",
        "understanding",
        "production",
        "transfer",
        "recognition",
        "production",
        "understanding",
    ]
    plan: list[dict[str, Any]] = []
    for index in range(candidate_count):
        point = points[index % len(points)]
        question_type = _planned_question_type(point, index)
        cognitive_level = levels[index % len(levels)]
        plan.append(
            {
                "knowledge_point_id": str(point.id),
                "knowledge_point_title": point.title,
                "question_type": question_type,
                "cognitive_level": cognitive_level,
                "difficulty": round(min(0.85, 0.3 + (index % 6) * 0.1), 2),
            }
        )
    return plan


async def generate_reviewed_unit_pool(
    *,
    db: AsyncSession,
    model_router: ModelRouter,
    learner_id: uuid.UUID | None,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    unit_title: str,
    points: list[KnowledgePoint],
    existing_stems: list[str],
    candidate_count: int = DEFAULT_POOL_SIZE,
) -> list[ExerciseQuestion]:
    if not points:
        raise UnitExerciseGenerationUnavailableError("Unit has no knowledge points")

    point_payloads = [_knowledge_point_payload(point) for point in points]
    point_by_id = {str(point.id): point for point in points}
    coverage_plan = build_coverage_plan(points, candidate_count=candidate_count)
    executor = PromptExecutor(db=db, model_router=model_router)
    result = await executor.execute(
        prompt_id="exercise.unit_candidates",
        version="v1",
        variables={
            "unit_title": unit_title,
            "candidate_count": candidate_count,
            "knowledge_points": point_payloads,
            "coverage_plan": coverage_plan,
            "existing_stems": existing_stems[-40:],
        },
        context=PromptExecutionContext(
            learner_id=learner_id,
            source_module="knowledge.unit_exercises",
            task_id="unit_exercise_candidates",
            target_type="curriculum_node",
            target_id=curriculum_node_id,
            metadata={"candidate_count": candidate_count, "generator": UNIT_GENERATOR_VERSION},
        ),
    )
    if result.decision != "accepted" or not isinstance(result.validated_output, dict):
        raise UnitExerciseGenerationUnavailableError("Candidate generation failed schema validation")

    raw_items = result.validated_output.get("items")
    if not isinstance(raw_items, list):
        raise UnitExerciseGenerationUnavailableError("Candidate generation returned no items")

    candidates = _deterministically_valid_candidates(raw_items, points=points)
    if len(candidates) < MIN_PUBLISHABLE_QUESTIONS:
        raise UnitExerciseGenerationUnavailableError("Too few candidates passed deterministic checks")

    reviewed = await _review_candidates(
        executor=executor,
        learner_id=learner_id,
        curriculum_node_id=curriculum_node_id,
        unit_title=unit_title,
        point_payloads=point_payloads,
        candidates=candidates,
    )
    if len(reviewed) < MIN_PUBLISHABLE_QUESTIONS:
        raise UnitExerciseGenerationUnavailableError("Too few candidates passed semantic review")
    reviewed_point_ids = {str(item.get("knowledgePointId") or "") for item in reviewed}
    planned_point_ids = {str(item["knowledge_point_id"]) for item in coverage_plan}
    missing_point_ids = planned_point_ids - reviewed_point_ids
    if missing_point_ids:
        raise UnitExerciseGenerationUnavailableError(
            "Reviewed candidate set does not cover every knowledge point"
        )
    quality_errors = lint_candidate_set(reviewed)
    if quality_errors:
        raise UnitExerciseGenerationUnavailableError(
            "Reviewed candidate set failed quality checks: " + ", ".join(quality_errors)
        )

    return [
        _candidate_to_question(
            candidate,
            point=point_by_id[candidate["knowledgePointId"]],
            source_id=source_id,
            curriculum_node_id=curriculum_node_id,
        )
        for candidate in reviewed
    ]


def lint_candidate(candidate: dict[str, Any], *, valid_point_ids: set[str]) -> list[str]:
    errors: list[str] = []
    point_id = str(candidate.get("knowledgePointId") or "")
    question_type = str(candidate.get("questionType") or "")
    stem = str(candidate.get("stem") or "").strip()
    answer = str(candidate.get("answer") or "").strip()
    explanation = str(candidate.get("explanation") or "").strip()
    options = _string_list(candidate.get("options"))
    scenario = candidate.get("scenario")
    target_expression = str(candidate.get("targetExpression") or "").strip()
    hint = str(candidate.get("hint") or "").strip()

    if point_id not in valid_point_ids:
        errors.append("unknown_knowledge_point")
    if question_type not in _QUESTION_TYPES:
        errors.append("unknown_question_type")
    if len(stem) < 18:
        errors.append("stem_too_short")
    if any(marker in stem for marker in _FORBIDDEN_STEM_MARKERS):
        errors.append("stem_leaks_target")
    if not answer:
        errors.append("missing_answer")
    if not target_expression:
        errors.append("missing_target_expression")
    if not hint:
        errors.append("missing_hint")
    if len(explanation) < 8 or _normalise(explanation) == _normalise(answer):
        errors.append("weak_explanation")
    if not isinstance(scenario, dict) or not all(
        str(scenario.get(key) or "").strip() for key in ("name", "setting", "zh")
    ):
        errors.append("missing_scenario")
    if question_type == "choice_context":
        if len(options) != 4 or len({_normalise(option) for option in options}) != 4:
            errors.append("choice_needs_four_unique_options")
        if sum(_normalise(option) == _normalise(answer) for option in options) != 1:
            errors.append("choice_answer_mismatch")
    elif question_type in {"fill_blank", "grammar_fill_blank", "dialogue_complete"}:
        if not any(marker in stem for marker in ("___", "____", "______")):
            errors.append("text_question_needs_blank")
        if options:
            errors.append("text_question_has_options")
    elif question_type == "error_fix" and options:
        errors.append("error_fix_has_options")
    return errors


def lint_candidate_set(candidates: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(candidates) < MIN_PUBLISHABLE_QUESTIONS:
        errors.append("set_needs_at_least_8_questions")
    type_counts = Counter(str(item.get("questionType") or "") for item in candidates)
    if len(type_counts) < 4:
        errors.append("set_needs_at_least_4_question_types")
    active_count = sum(str(item.get("questionType")) in _ACTIVE_TYPES for item in candidates)
    if candidates and active_count / len(candidates) < 0.5:
        errors.append("set_needs_50_percent_active_input")
    recognition_count = sum(item.get("cognitiveLevel") == "recognition" for item in candidates)
    if candidates and recognition_count / len(candidates) > 0.25:
        errors.append("set_has_too_much_recognition")
    advanced_count = sum(
        item.get("cognitiveLevel") in {"production", "transfer"} for item in candidates
    )
    if candidates and advanced_count / len(candidates) < 0.5:
        errors.append("set_needs_50_percent_production_or_transfer")
    stems = [_normalise(str(item.get("stem") or "")) for item in candidates]
    if len(stems) != len(set(stems)):
        errors.append("set_has_duplicate_stems")
    return errors


def select_exercises_for_learner(
    questions: list[ExerciseQuestion],
    *,
    mastery_by_point: dict[uuid.UUID, float],
    limit: int,
) -> list[ExerciseQuestion]:
    """Select a stable, diverse set while adapting difficulty to point mastery."""
    if len(questions) <= limit:
        return questions

    def score(question: ExerciseQuestion) -> tuple[float, str]:
        mastery = mastery_by_point.get(question.knowledge_point_id, 0.35)
        target_difficulty = min(0.8, max(0.3, 0.35 + mastery * 0.45))
        quality = question.quality_score
        quality_score = float(quality) if isinstance(quality, int | float) else 0.72
        rank_score = abs(question.difficulty - target_difficulty) * 0.55 + (1 - quality_score) * 0.45
        return (rank_score, str(question.id))

    ranked = sorted(questions, key=score)
    selected: list[ExerciseQuestion] = []
    seen_types: set[str] = set()
    seen_points: set[uuid.UUID | None] = set()
    for question in ranked:
        if len(selected) >= limit:
            break
        if question.question_type not in seen_types:
            selected.append(question)
            seen_types.add(question.question_type)
            seen_points.add(question.knowledge_point_id)
    for question in ranked:
        if len(selected) >= limit:
            break
        if question not in selected and question.knowledge_point_id not in seen_points:
            selected.append(question)
            seen_types.add(question.question_type)
            seen_points.add(question.knowledge_point_id)
    for question in ranked:
        if len(selected) >= limit:
            break
        if question not in selected:
            selected.append(question)
    return selected


async def select_unit_exercises_for_learner(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID | None,
    questions: list[ExerciseQuestion],
    limit: int,
) -> list[ExerciseQuestion]:
    point_ids = {
        question.knowledge_point_id
        for question in questions
        if question.knowledge_point_id is not None
    }
    mastery_by_point: dict[uuid.UUID, float] = {}
    if point_ids:
        result = await db.execute(
            select(LearnerKnowledgeState).where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.knowledge_point_id.in_(point_ids),
            )
        )
        mastery_by_point = {
            state.knowledge_point_id: state.mastery_score for state in result.scalars().all()
        }
    return select_exercises_for_learner(
        questions,
        mastery_by_point=mastery_by_point,
        limit=limit,
    )


async def _review_candidates(
    *,
    executor: PromptExecutor,
    learner_id: uuid.UUID | None,
    curriculum_node_id: uuid.UUID,
    unit_title: str,
    point_payloads: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_result = await executor.execute(
        prompt_id="exercise.unit_review",
        version="v1",
        variables={
            "unit_title": unit_title,
            "knowledge_points": point_payloads,
            "candidates": candidates,
        },
        context=PromptExecutionContext(
            learner_id=learner_id,
            source_module="knowledge.unit_exercises",
            task_id="unit_exercise_review",
            target_type="curriculum_node",
            target_id=curriculum_node_id,
            metadata={"candidate_count": len(candidates), "generator": UNIT_GENERATOR_VERSION},
        ),
    )
    if review_result.decision != "accepted" or not isinstance(
        review_result.validated_output, dict
    ):
        raise UnitExerciseGenerationUnavailableError("Candidate review failed schema validation")
    reviews = review_result.validated_output.get("reviews")
    if not isinstance(reviews, list):
        raise UnitExerciseGenerationUnavailableError("Candidate review returned no reviews")
    if len(reviews) != len(candidates):
        raise UnitExerciseGenerationUnavailableError("Candidate review count does not match items")

    decisions: dict[int, dict[str, Any]] = {}
    for review in reviews:
        if isinstance(review, dict) and isinstance(review.get("index"), int):
            if review["index"] in decisions:
                raise UnitExerciseGenerationUnavailableError(
                    "Candidate review contains duplicate indexes"
                )
            decisions[review["index"]] = review
    if set(decisions) != set(range(len(candidates))):
        raise UnitExerciseGenerationUnavailableError("Candidate review did not cover every item")

    accepted: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        review = decisions[index]
        scores = review.get("scores") if isinstance(review.get("scores"), dict) else {}
        quality_score = _quality_score(scores)
        hard_gate_passed = (
            float(scores.get("knowledgeAlignment", 0)) >= 0.75
            and float(scores.get("answerability", 0)) >= 0.75
        )
        if review.get("decision") == "accept" and hard_gate_passed:
            accepted.append(
                {
                    **candidate,
                    "review": {
                        "decision": "accept",
                        "reasons": _string_list(review.get("reasons")),
                        "scores": scores,
                        "qualityScore": quality_score,
                    },
                }
            )
    return accepted


def _deterministically_valid_candidates(
    raw_items: list[Any],
    *,
    points: list[KnowledgePoint],
) -> list[dict[str, Any]]:
    point_ids = {str(point.id) for point in points}
    candidates: list[dict[str, Any]] = []
    seen_stems: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        candidate = dict(raw_item)
        answer = str(candidate.get("answer") or "").strip()
        acceptable = _string_list(candidate.get("acceptableAnswers"))
        if answer and all(_normalise(item) != _normalise(answer) for item in acceptable):
            acceptable.insert(0, answer)
        candidate["acceptableAnswers"] = acceptable
        errors = lint_candidate(candidate, valid_point_ids=point_ids)
        normalised_stem = _normalise(str(candidate.get("stem") or ""))
        if errors or normalised_stem in seen_stems:
            continue
        seen_stems.add(normalised_stem)
        candidates.append(candidate)
    return candidates


def _candidate_to_question(
    candidate: dict[str, Any],
    *,
    point: KnowledgePoint,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
) -> ExerciseQuestion:
    question_type = str(candidate["questionType"])
    rubric = {
        "target_expression": str(candidate["targetExpression"]).strip(),
        "acceptable_answers": _string_list(candidate["acceptableAnswers"]),
        "error_types": _string_list(candidate["errorTypes"]),
        "hint": str(candidate["hint"]).strip(),
    }
    review = candidate.get("review") if isinstance(candidate.get("review"), dict) else {}
    quality_score = float(review.get("qualityScore") or 0.0)
    quality_dimensions = review.get("scores") if isinstance(review.get("scores"), dict) else {}
    return ExerciseQuestion(
        source_id=source_id,
        curriculum_node_id=curriculum_node_id,
        knowledge_point_id=point.id,
        question_type=question_type,
        stem=str(candidate["stem"]).strip(),
        options=_string_list(candidate["options"]),
        answer=str(candidate["answer"]).strip(),
        explanation=str(candidate["explanation"]).strip(),
        difficulty=float(candidate["difficulty"]),
        quality_score=quality_score,
        quality_status="accepted",
        generator_version=UNIT_GENERATOR_VERSION,
        quality_dimensions=quality_dimensions,
        status="published",
        metadata_={
            "generator": UNIT_GENERATOR_VERSION,
            "generator_version": UNIT_GENERATOR_VERSION,
            "quality_gate": {"status": "accepted", "review": review},
            "cognitive_level": candidate["cognitiveLevel"],
            "interaction": {
                "type": question_type,
                "input_mode": "choice" if question_type == "choice_context" else "text",
                "allow_retry": True,
                "hint_levels": 2,
            },
            "scenario": candidate["scenario"],
            "rubric": rubric,
            "source": {
                "knowledge_point_id": str(point.id),
                "page_number": point.source_page,
                "evidence": point.summary,
            },
            "source_type": "generated",
            "generated_from": {
                "source_id": str(source_id),
                "curriculum_node_id": str(curriculum_node_id),
                "knowledge_point_id": str(point.id),
                "parser_run_id": (point.content or {}).get("parser_run_id"),
            },
        },
    )


def _planned_question_type(point: KnowledgePoint, index: int) -> str:
    cycle = [
        "dialogue_complete",
        "error_fix",
        "choice_context",
        "fill_blank",
        "dialogue_complete",
        "choice_context",
        "grammar_fill_blank",
        "error_fix",
    ]
    planned = cycle[index % len(cycle)]
    if planned == "grammar_fill_blank" and point.type not in {"grammar", "sentence_pattern"}:
        return "fill_blank"
    return planned


def _knowledge_point_payload(point: KnowledgePoint) -> dict[str, Any]:
    content = point.content if isinstance(point.content, dict) else {}
    return {
        "id": str(point.id),
        "type": point.type,
        "title": point.title,
        "summary": point.summary,
        "difficulty": point.difficulty,
        "source_page": point.source_page,
        "examples": content.get("examples", []),
        "common_errors": content.get("common_errors", []),
    }


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value.casefold()).strip()


def _quality_score(scores: dict[str, Any]) -> float:
    weights = {
        "knowledgeAlignment": 0.30,
        "answerability": 0.25,
        "naturalness": 0.15,
        "distractorQuality": 0.10,
        "explanationQuality": 0.10,
        "novelty": 0.10,
    }
    value = sum(float(scores.get(name, 0.0)) * weight for name, weight in weights.items())
    return round(min(1.0, max(0.0, value)), 4)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
