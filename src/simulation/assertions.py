from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssertionResult:
    passed: bool
    message: str


class AssertionEngine:
    """Small assertion evaluator for simulation step outputs."""

    def evaluate(
        self,
        assertions: list[dict[str, Any]],
        output: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> list[AssertionResult]:
        return [self._evaluate_one(assertion, output, context) for assertion in assertions]

    def _evaluate_one(
        self,
        assertion: dict[str, Any],
        output: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AssertionResult:
        kind = assertion.get("type")
        path = assertion.get("path")
        source = context if assertion.get("source") == "context" else output
        value = _lookup(source, str(path)) if path else source

        if kind == "status_code":
            expected = assertion.get("equals", 200)
            return AssertionResult(value == expected, f"{path} expected {expected}, got {value}")
        if kind == "exists":
            return AssertionResult(value is not None, f"{path} should exist")
        if kind == "not_empty":
            return AssertionResult(bool(value), f"{path} should not be empty")
        if kind == "equals":
            expected = assertion.get("value")
            return AssertionResult(value == expected, f"{path} expected {expected!r}, got {value!r}")
        if kind == "contains":
            expected = assertion.get("value")
            passed = isinstance(value, list | str | dict) and expected in value
            return AssertionResult(passed, f"{path} should contain {expected!r}")
        if kind == "gte":
            expected = assertion.get("value", 0)
            passed = isinstance(value, int | float) and value >= expected
            return AssertionResult(passed, f"{path} expected >= {expected}, got {value!r}")
        if kind == "event_exists":
            event_type = assertion.get("event_type")
            passed = _event_index(value, str(event_type)) is not None
            return AssertionResult(passed, f"{path} should include event_type {event_type!r}")
        if kind == "event_absent":
            event_type = assertion.get("event_type")
            passed = _event_index(value, str(event_type)) is None
            return AssertionResult(passed, f"{path} should not include event_type {event_type!r}")
        if kind == "event_order":
            before = assertion.get("before")
            after = assertion.get("after")
            before_index = _event_index(value, str(before))
            after_index = _event_index(value, str(after))
            passed = before_index is not None and after_index is not None and before_index < after_index
            return AssertionResult(
                passed,
                f"{path} expected event {before!r} before {after!r}",
            )
        if kind == "tool_called":
            tool_name = assertion.get("tool_name")
            passed = _tool_index(value, str(tool_name)) is not None
            return AssertionResult(passed, f"{path} should include tool_name {tool_name!r}")
        if kind == "tool_success_rate_gte":
            threshold = assertion.get("threshold", 1.0)
            rate = _tool_success_rate(value)
            passed = isinstance(threshold, int | float) and rate >= float(threshold)
            return AssertionResult(passed, f"{path} tool success rate expected >= {threshold}, got {rate}")
        if kind == "value_between":
            lower = assertion.get("min")
            upper = assertion.get("max")
            passed = (
                isinstance(value, int | float)
                and isinstance(lower, int | float)
                and isinstance(upper, int | float)
                and float(lower) <= float(value) <= float(upper)
            )
            return AssertionResult(passed, f"{path} expected between {lower} and {upper}, got {value!r}")
        if kind == "delta_gte":
            threshold = assertion.get("threshold", 0)
            passed = isinstance(value, int | float) and isinstance(threshold, int | float) and value >= threshold
            return AssertionResult(passed, f"{path} expected delta >= {threshold}, got {value!r}")
        if kind == "evidence_ref_exists":
            passed = _has_evidence_refs(value)
            return AssertionResult(passed, f"{path} should include non-empty evidence refs")
        if kind == "verification_check_passed":
            check_name = assertion.get("check_name")
            passed = _verification_check_passed(value, str(check_name))
            return AssertionResult(passed, f"{path} should include passed check {check_name!r}")
        if kind == "memory_event_type_exists":
            event_type = assertion.get("event_type")
            passed = _event_index(value, str(event_type)) is not None
            return AssertionResult(passed, f"{path} should include memory event_type {event_type!r}")
        if kind == "recommendation_contains_capability":
            capability_id = assertion.get("capability_id")
            passed = _recommendation_contains_capability(value, str(capability_id))
            return AssertionResult(passed, f"{path} should include capability_id {capability_id!r}")
        if kind == "no_unexpected_error":
            error = _find_unexpected_error(value)
            return AssertionResult(error is None, error or "No unexpected error")
        return AssertionResult(False, f"Unknown assertion type: {kind}")


def _lookup(source: Mapping[str, Any], path: str) -> Any:
    current: Any = source
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
    return current


def _event_index(value: Any, event_type: str) -> int | None:
    if not isinstance(value, list):
        return None
    for index, item in enumerate(value):
        if isinstance(item, Mapping) and item.get("event_type") == event_type:
            return index
    return None


def _tool_index(value: Any, tool_name: str) -> int | None:
    if not isinstance(value, list):
        return None
    for index, item in enumerate(value):
        if isinstance(item, Mapping) and item.get("tool_name") == tool_name:
            return index
    return None


def _tool_success_rate(value: Any) -> float:
    if not isinstance(value, list) or not value:
        return 0.0
    successes = 0
    total = 0
    for item in value:
        if not isinstance(item, Mapping):
            continue
        total += 1
        status = str(item.get("status", "")).casefold()
        if item.get("success") is True or status in {"success", "passed", "completed"}:
            successes += 1
    return successes / total if total else 0.0


def _has_evidence_refs(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, Mapping):
        refs = value.get("evidence_refs") or value.get("evidence")
        return bool(refs)
    return False


def _verification_check_passed(value: Any, check_name: str) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name") or item.get("check_name") or item.get("id")
        if name != check_name:
            continue
        status = str(item.get("status", "")).casefold()
        return item.get("passed") is True or status == "passed"
    return False


def _recommendation_contains_capability(value: Any, capability_id: str) -> bool:
    if isinstance(value, Mapping):
        value = value.get("recommendations") or value.get("items") or value.get("data")
    if not isinstance(value, list):
        return False
    return any(
        isinstance(item, Mapping)
        and (item.get("capability_id") == capability_id or item.get("feature_id") == capability_id)
        for item in value
    )


def _find_unexpected_error(value: Any, path: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).casefold()
            child_path = f"{path}.{key}"
            if key_text in {"error", "exception", "traceback"} and item:
                return f"{child_path} contains unexpected error: {item!r}"
            if key_text == "status" and str(item).casefold() in {"failed", "error"}:
                return f"{child_path} has failed status"
            if key_text == "status_code" and isinstance(item, int) and item >= 500:
                return f"{child_path} has server error status code {item}"
            nested = _find_unexpected_error(item, child_path)
            if nested:
                return nested
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested = _find_unexpected_error(item, f"{path}.{index}")
            if nested:
                return nested
    return None
