import uuid

from src.knowledge.exercise_grader import grade_exercise_answer
from src.models.knowledge import ExerciseQuestion


def test_grader_returns_hint_retry_and_review_signal_for_wrong_text_answer() -> None:
    question = ExerciseQuestion(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        question_type="fill_blank",
        stem="A: What's your name? B: ______",
        options=[],
        answer="I'm Linda.",
        explanation="使用 I'm 加名字进行自我介绍。",
        difficulty=0.3,
        status="published",
        metadata_={
            "interaction": {"input_mode": "text", "allow_retry": True},
            "rubric": {
                "target_expression": "I'm Linda.",
                "acceptable_answers": ["I'm Linda.", "I am Linda."],
                "error_types": ["word_order", "missing_be"],
                "hint": "使用 I am 或 I'm 加名字。",
            },
        },
    )

    result = grade_exercise_answer(question, "I name Linda", attempt_index=0)

    assert result["correct"] is False
    assert result["can_retry"] is True
    assert result["hint"]
    assert result["error_type"]
    assert result["next_review_signal"] in {"soon", "urgent"}
