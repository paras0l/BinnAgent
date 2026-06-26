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
        value = _lookup(source, str(path)) if path else None

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
