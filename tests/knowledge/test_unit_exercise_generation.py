import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.knowledge.unit_exercise_generation import (
    UNIT_GENERATOR_VERSION,
    UnitExerciseGenerationUnavailableError,
    build_coverage_plan,
    generate_reviewed_unit_pool,
    lint_candidate,
    lint_candidate_set,
    select_exercises_for_learner,
    select_generation_points,
)
from src.models.knowledge import ExerciseQuestion, KnowledgePoint
from src.providers.base import ChatResponse


def _point(title: str, point_type: str = "phrase") -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        canonical_key=f"{point_type}.{uuid.uuid4()}",
        type=point_type,
        title=title,
        summary=f"正确使用 {title}",
        source_page="P.2",
        difficulty=0.3,
        status="published",
        content={"examples": [title]},
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    return point


def _candidates(point: KnowledgePoint) -> list[dict]:
    types = [
        "dialogue_complete",
        "error_fix",
        "choice_context",
        "fill_blank",
        "dialogue_complete",
        "choice_context",
        "grammar_fill_blank",
        "error_fix",
    ]
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
    items: list[dict] = []
    for index, (question_type, level) in enumerate(zip(types, levels, strict=True)):
        stem = f"It is 7:{index}0 a.m. Complete this meaningful classroom task number {index}."
        options: list[str] = []
        if question_type in {"dialogue_complete", "fill_blank", "grammar_fill_blank"}:
            stem += " A: Good morning! B: ______"
        elif question_type == "error_fix":
            stem += " Correct this sentence: Good night, teacher."
        else:
            stem += " Which greeting is appropriate?"
            options = ["Good morning!", "Good afternoon!", "Good evening!", "Good night!"]
        items.append(
            {
                "knowledgePointId": str(point.id),
                "questionType": question_type,
                "cognitiveLevel": level,
                "scenario": {
                    "name": f"scenario-{index}",
                    "setting": "meeting before the first class",
                    "zh": "早晨上课前",
                },
                "stem": stem,
                "options": options,
                "answer": "Good morning!",
                "acceptableAnswers": ["Good morning!"],
                "explanation": "题目时间是上午，因此应该使用早晨问候语。",
                "difficulty": 0.3 + index * 0.05,
                "targetExpression": point.title,
                "errorTypes": ["context_mismatch"],
                "hint": "关注题目中的时间线索。",
            }
        )
    return items


def _review(index: int, *, decision: str = "accept", reasons: list[str] | None = None) -> dict:
    return {
        "index": index,
        "decision": decision,
        "reasons": reasons or [],
        "scores": {
            "knowledgeAlignment": 0.95 if decision == "accept" else 0.5,
            "answerability": 0.95 if decision == "accept" else 0.4,
            "naturalness": 0.9,
            "distractorQuality": 0.85,
            "explanationQuality": 0.9,
            "novelty": 0.8,
        },
    }


def test_coverage_plan_limits_recall_and_prioritises_active_use() -> None:
    points = [_point("Good morning!"), _point("be 动词", "grammar")]

    plan = build_coverage_plan(points, candidate_count=16)

    assert len(plan) == 16
    assert sum(item["cognitive_level"] == "recognition" for item in plan) / len(plan) <= 0.25
    assert sum(
        item["cognitive_level"] in {"production", "transfer"} for item in plan
    ) / len(plan) >= 0.5
    assert {item["knowledge_point_id"] for item in plan} == {str(point.id) for point in points}


def test_generation_point_selection_does_not_let_vocabulary_hide_core_patterns() -> None:
    vocabulary = [_point(f"word-{index}", "vocabulary") for index in range(20)]
    patterns = [_point("How are you?", "sentence_pattern"), _point("be 动词", "grammar")]
    phrases = [_point("I'm fine, thanks.", "phrase")]

    selected = select_generation_points([*vocabulary, *patterns, *phrases], limit=8)

    assert all(point in selected for point in [*patterns, *phrases])
    assert sum(point.type == "vocabulary" for point in selected) == 5


def test_linter_rejects_old_template_that_leaks_target_and_mismatches_context() -> None:
    point = _point("I'm fine, thanks.")
    candidate = _candidates(point)[0]
    candidate["stem"] = (
        "场景：课堂问答。A: Hello! I am Jack. B: ______ "
        "目标：使用「I'm fine, thanks.」相关表达。"
    )

    errors = lint_candidate(candidate, valid_point_ids={str(point.id)})

    assert "stem_leaks_target" in errors


def test_candidate_set_requires_cognitive_and_interaction_diversity() -> None:
    point = _point("Good morning!")
    candidates = _candidates(point)

    assert lint_candidate_set(candidates) == []

    for candidate in candidates:
        candidate["questionType"] = "choice_context"
        candidate["cognitiveLevel"] = "recognition"
    errors = lint_candidate_set(candidates)
    assert "set_needs_at_least_4_question_types" in errors
    assert "set_has_too_much_recognition" in errors


@pytest.mark.asyncio
async def test_generation_publishes_only_schema_valid_reviewed_candidates() -> None:
    point = _point("Good morning!")
    candidates = _candidates(point)
    reviews = [_review(index) for index in range(len(candidates))]
    model_router = AsyncMock()
    model_router.chat.side_effect = [
        ChatResponse(provider="test", model="test", content=json.dumps({"items": candidates})),
        ChatResponse(provider="test", model="test", content=json.dumps({"reviews": reviews})),
    ]
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    questions = await generate_reviewed_unit_pool(
        db=db,
        model_router=model_router,
        learner_id=uuid.uuid4(),
        source_id=point.source_id,
        curriculum_node_id=point.curriculum_node_id,
        unit_title="Starter Unit 1",
        points=[point],
        existing_stems=[],
        candidate_count=8,
    )

    assert len(questions) == 8
    assert all(question.status == "published" for question in questions)
    assert all(question.metadata_["generator_version"] == UNIT_GENERATOR_VERSION for question in questions)
    assert all(question.metadata_["quality_gate"]["status"] == "accepted" for question in questions)
    assert [call.args[0].task_type for call in model_router.chat.await_args_list] == [
        "exercise.unit_candidates",
        "exercise.unit_review",
    ]


@pytest.mark.asyncio
async def test_generation_does_not_publish_semantically_rejected_candidates() -> None:
    point = _point("I'm fine, thanks.")
    candidates = _candidates(point)
    candidates[0]["stem"] = "A: Hello! I am Jack. B: ______"
    reviews = [
        _review(
            index,
            decision="reject" if index == 0 else "accept",
            reasons=["答案没有自然回应自我介绍"] if index == 0 else [],
        )
        for index in range(len(candidates))
    ]
    model_router = AsyncMock()
    model_router.chat.side_effect = [
        ChatResponse(provider="test", model="test", content=json.dumps({"items": candidates})),
        ChatResponse(provider="test", model="test", content=json.dumps({"reviews": reviews})),
    ]
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    with pytest.raises(UnitExerciseGenerationUnavailableError, match="semantic review"):
        await generate_reviewed_unit_pool(
            db=db,
            model_router=model_router,
            learner_id=uuid.uuid4(),
            source_id=point.source_id,
            curriculum_node_id=point.curriculum_node_id,
            unit_title="Starter Unit 1",
            points=[point],
            existing_stems=[],
            candidate_count=8,
        )


def test_selector_raises_target_difficulty_for_high_mastery() -> None:
    point = _point("Good morning!")
    questions: list[ExerciseQuestion] = []
    for index, difficulty in enumerate((0.2, 0.35, 0.55, 0.8)):
        question = ExerciseQuestion(
            source_id=point.source_id,
            curriculum_node_id=point.curriculum_node_id,
            knowledge_point_id=point.id,
            question_type=f"type-{index}",
            stem=f"Question {index} with enough context",
            options=[],
            answer="answer",
            explanation="explanation",
            difficulty=difficulty,
            status="published",
            metadata_={},
        )
        question.id = uuid.uuid4()
        questions.append(question)

    low_mastery = select_exercises_for_learner(
        questions,
        mastery_by_point={point.id: 0.0},
        limit=2,
    )
    high_mastery = select_exercises_for_learner(
        questions,
        mastery_by_point={point.id: 1.0},
        limit=2,
    )

    assert sum(question.difficulty for question in high_mastery) > sum(
        question.difficulty for question in low_mastery
    )
