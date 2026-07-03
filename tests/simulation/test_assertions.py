from src.simulation.assertions import AssertionEngine


def _passed(assertion: dict, output: dict) -> bool:
    return AssertionEngine().evaluate([assertion], output, {})[0].passed


def test_legacy_assertions_still_pass() -> None:
    output = {"status_code": 200, "json": {"id": "1", "items": ["a"], "score": 2}}

    assert _passed({"type": "status_code", "path": "status_code", "equals": 200}, output)
    assert _passed({"type": "exists", "path": "json.id"}, output)
    assert _passed({"type": "not_empty", "path": "json.items"}, output)
    assert _passed({"type": "equals", "path": "json.id", "value": "1"}, output)
    assert _passed({"type": "contains", "path": "json.items", "value": "a"}, output)
    assert _passed({"type": "gte", "path": "json.score", "value": 1}, output)


def test_event_exists_success_and_failure() -> None:
    output = {"events": [{"event_type": "exercise_graded"}]}

    assert _passed({"type": "event_exists", "path": "events", "event_type": "exercise_graded"}, output)
    assert not _passed({"type": "event_exists", "path": "events", "event_type": "memory_written"}, output)


def test_event_order_success_and_failure() -> None:
    output = {
        "events": [
            {"event_type": "learner_answer_received"},
            {"event_type": "exercise_graded"},
            {"event_type": "mastery_updated"},
        ]
    }

    assert _passed(
        {"type": "event_order", "path": "events", "before": "exercise_graded", "after": "mastery_updated"},
        output,
    )
    assert not _passed(
        {"type": "event_order", "path": "events", "before": "mastery_updated", "after": "exercise_graded"},
        output,
    )


def test_tool_called_success_and_failure() -> None:
    output = {"tool_calls": [{"tool_name": "mastery.update", "status": "success"}]}

    assert _passed({"type": "tool_called", "path": "tool_calls", "tool_name": "mastery.update"}, output)
    assert not _passed({"type": "tool_called", "path": "tool_calls", "tool_name": "memory.write"}, output)


def test_tool_success_rate_gte_success_and_failure() -> None:
    output = {
        "tool_calls": [
            {"tool_name": "exercise.grade", "status": "success"},
            {"tool_name": "mastery.update", "status": "failed"},
        ]
    }

    assert _passed({"type": "tool_success_rate_gte", "path": "tool_calls", "threshold": 0.5}, output)
    assert not _passed({"type": "tool_success_rate_gte", "path": "tool_calls", "threshold": 1.0}, output)


def test_value_between_success_and_failure() -> None:
    output = {"mastery_update": {"new_score": 0.7}}

    assert _passed(
        {"type": "value_between", "path": "mastery_update.new_score", "min": 0, "max": 1},
        output,
    )
    assert not _passed(
        {"type": "value_between", "path": "mastery_update.new_score", "min": 0.8, "max": 1},
        output,
    )


def test_delta_gte_success_and_failure() -> None:
    output = {"mastery_update": {"mastery_delta": 0.03}}

    assert _passed(
        {"type": "delta_gte", "path": "mastery_update.mastery_delta", "threshold": 0.01},
        output,
    )
    assert not _passed(
        {"type": "delta_gte", "path": "mastery_update.mastery_delta", "threshold": 0.05},
        output,
    )


def test_evidence_ref_exists_success_and_failure() -> None:
    output = {"mastery_update": {"evidence_refs": [{"type": "exercise", "id": "q1"}]}, "empty": []}

    assert _passed({"type": "evidence_ref_exists", "path": "mastery_update.evidence_refs"}, output)
    assert not _passed({"type": "evidence_ref_exists", "path": "empty"}, output)


def test_verification_check_passed_success_and_failure() -> None:
    output = {"checks": [{"name": "mastery_update_valid", "passed": True}]}

    assert _passed(
        {
            "type": "verification_check_passed",
            "path": "checks",
            "check_name": "mastery_update_valid",
        },
        output,
    )
    assert not _passed(
        {"type": "verification_check_passed", "path": "checks", "check_name": "memory_written"},
        output,
    )


def test_memory_event_type_exists_success_and_failure() -> None:
    output = {"events": [{"event_type": "memory_written"}]}

    assert _passed({"type": "memory_event_type_exists", "path": "events", "event_type": "memory_written"}, output)
    assert not _passed({"type": "memory_event_type_exists", "path": "events", "event_type": "review_scheduled"}, output)


def test_recommendation_contains_capability_success_and_failure() -> None:
    output = {"recommendations": [{"capability_id": "grammar-explain"}]}

    assert _passed(
        {
            "type": "recommendation_contains_capability",
            "path": "recommendations",
            "capability_id": "grammar-explain",
        },
        output,
    )
    assert not _passed(
        {
            "type": "recommendation_contains_capability",
            "path": "recommendations",
            "capability_id": "word-parts",
        },
        output,
    )


def test_no_unexpected_error_success_and_failure() -> None:
    assert _passed({"type": "no_unexpected_error"}, {"status": "completed", "status_code": 200})
    assert not _passed({"type": "no_unexpected_error"}, {"error": "boom"})
