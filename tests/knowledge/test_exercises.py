import uuid
from datetime import datetime, timezone

from src.knowledge.exercise_blueprints import build_exercise_blueprints
from src.knowledge.exercise_generator import build_question
from src.knowledge.exercise_grader import grade_exercise_answer
from src.knowledge.exercise_linter import lint_exercise_set
from src.models.knowledge import KnowledgePoint


def _point(title: str, index: int = 1) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        canonical_key=f"point.{index}",
        type="phrase",
        title=title,
        summary=f"用于练习 {title} 的真实表达。",
        source_page=f"P.{index}",
        status="published",
        difficulty=0.2,
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    return point


def test_blueprint_generator_creates_mixed_contextual_exercise_set() -> None:
    points = [_point("Good morning!", 1), _point("I'm Linda.", 2)]
    questions = [
        build_question(
            blueprint,
            source_id=points[0].source_id,
            curriculum_node_id=points[0].curriculum_node_id,
            peers=points,
        )
        for blueprint in build_exercise_blueprints(points)
    ]

    assert len(questions) == 8
    assert {question.question_type for question in questions} == {
        "choice_context",
        "fill_blank",
        "dialogue_complete",
        "error_fix",
    }
    assert sum(not question.options for question in questions) / len(questions) >= 0.3
    assert not lint_exercise_set(questions)
    assert all((question.metadata_ or {}).get("scenario") for question in questions)
    assert all((question.metadata_ or {}).get("rubric") for question in questions)


def test_grader_returns_hint_retry_and_review_signal_for_wrong_text_answer() -> None:
    point = _point("I'm Linda.", 1)
    blueprint = build_exercise_blueprints([point])[1]
    question = build_question(
        blueprint,
        source_id=point.source_id,
        curriculum_node_id=point.curriculum_node_id,
        peers=[point],
    )

    result = grade_exercise_answer(question, "I name Linda", attempt_index=0)

    assert result["correct"] is False
    assert result["can_retry"] is True
    assert result["hint"]
    assert result["error_type"]
    assert result["next_review_signal"] in {"soon", "urgent"}
