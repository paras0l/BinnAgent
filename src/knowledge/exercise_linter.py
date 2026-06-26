from src.models.knowledge import ExerciseQuestion

TEMPLATE_PHRASES = [
    "下列哪一项最符合这个教材知识点",
    "以上都不正确",
    "需要结合更多上下文判断",
]

ACTIVE_INPUT_TYPES = {"fill_blank", "dialogue_complete", "error_fix"}


def lint_question(question: ExerciseQuestion) -> list[str]:
    errors: list[str] = []
    metadata = question.metadata_ or {}
    interaction = metadata.get("interaction") or {}
    rubric = metadata.get("rubric") or {}
    scenario = metadata.get("scenario") or {}

    if any(phrase in question.stem for phrase in TEMPLATE_PHRASES):
        errors.append("stem_is_template")
    if not scenario:
        errors.append("missing_scenario")
    if not question.answer.strip():
        errors.append("missing_answer")
    if not rubric.get("acceptable_answers") and not rubric.get("target_expression"):
        errors.append("missing_rubric")
    if question.question_type == "choice_context" and len(question.options or []) < 2:
        errors.append("choice_needs_options")
    if question.question_type in ACTIVE_INPUT_TYPES and interaction.get("input_mode") != "text":
        errors.append("active_input_must_use_text")
    if question.explanation.strip() == question.answer.strip():
        errors.append("explanation_repeats_answer")
    return errors


def lint_exercise_set(questions: list[ExerciseQuestion]) -> list[str]:
    errors: list[str] = []
    if len(questions) < 8:
        errors.append("set_needs_at_least_8_questions")
    if len({question.question_type for question in questions}) < 4:
        errors.append("set_needs_at_least_4_question_types")

    active_count = sum(question.question_type in ACTIVE_INPUT_TYPES for question in questions)
    if questions and active_count / len(questions) < 0.3:
        errors.append("set_needs_30_percent_active_input")

    streak_type = None
    streak_count = 0
    for question in questions:
        if question.question_type == streak_type:
            streak_count += 1
        else:
            streak_type = question.question_type
            streak_count = 1
        if streak_count >= 3:
            errors.append("set_has_three_same_types_in_a_row")
            break

    for index, question in enumerate(questions, start=1):
        for error in lint_question(question):
            errors.append(f"question_{index}:{error}")
    return errors
