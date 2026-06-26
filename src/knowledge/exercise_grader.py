from typing import Any


def answer_to_text(answer: str | dict[str, Any]) -> str:
    if isinstance(answer, str):
        return answer.strip()
    value = answer.get("value")
    if isinstance(value, str):
        return value.strip()
    items = answer.get("items")
    if isinstance(items, list):
        return " ".join(str(item).strip() for item in items if str(item).strip())
    pairs = answer.get("pairs")
    if isinstance(pairs, list):
        return "; ".join(str(pair) for pair in pairs)
    return ""


def _normalize(value: str) -> str:
    return " ".join(value.strip().strip(".!?。！？").casefold().split())


def grade_exercise_answer(question, answer: str | dict[str, Any], *, attempt_index: int = 0) -> dict[str, Any]:
    submitted = answer_to_text(answer)
    metadata = question.metadata_ or {}
    rubric = metadata.get("rubric") or {}
    acceptable = rubric.get("acceptable_answers") or [question.answer]
    normalized = _normalize(submitted)
    normalized_acceptable = {_normalize(str(item)) for item in acceptable}
    target = _normalize(str(rubric.get("target_expression") or question.answer))

    correct = normalized in normalized_acceptable
    used_target = bool(target and target in normalized)
    meaning_clear = correct or used_target
    score = 1.0 if correct else 0.6 if meaning_clear else 0.0
    passed = score >= 0.7

    error_types = rubric.get("error_types") or ["needs_review"]
    error_type = None if correct else str(error_types[0])
    hint = None if correct else rubric.get("hint") or "回到场景，先想你真正要表达的意思。"
    can_retry = not correct and attempt_index < 1
    next_review_signal = "later" if correct else "soon" if score >= 0.5 else "urgent"

    if correct:
        feedback = "回答正确。你能在这个场景里使用目标表达。"
    elif meaning_clear:
        feedback = "意思接近，但表达还不够自然。请根据提示再试一次。"
    else:
        feedback = "这次还没有抓住目标表达。先看提示，再换一种更自然的说法。"

    return {
        "submitted_answer": submitted,
        "correct": correct,
        "score": score,
        "passed": passed,
        "error_type": error_type,
        "feedback": feedback,
        "hint": hint,
        "can_retry": can_retry,
        "next_review_signal": next_review_signal,
        "rubric": {
            "used_target_expression": used_target,
            "meaning_clear": meaning_clear,
            "acceptable_answers": acceptable,
        },
    }
