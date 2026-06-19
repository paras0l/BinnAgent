from src.vocabulary.learning import canonical_vocabulary_key, spelling_feedback


def test_canonical_key_normalizes_case_spacing_and_smart_apostrophe() -> None:
    assert canonical_vocabulary_key("  What’s   this? ") == "what's this"


def test_spelling_feedback_reports_omission() -> None:
    error_type, diff, message = spelling_feedback("mornng", "morning")

    assert error_type == "omission"
    assert any(item == {"answer": None, "correct": "i", "status": "missing"} for item in diff)
    assert "i" in message


def test_spelling_feedback_reports_transposition() -> None:
    error_type, _, message = spelling_feedback("freind", "friend")

    assert error_type == "transposition"
    assert "顺序" in message


def test_spelling_feedback_accepts_exact_answer() -> None:
    error_type, diff, message = spelling_feedback("hello", "hello")

    assert error_type is None
    assert all(item["status"] == "match" for item in diff)
    assert message == "拼对了"
