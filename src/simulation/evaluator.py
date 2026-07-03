import math
from collections.abc import Mapping
from typing import Any

from src.simulation.scenario import SimulationMode, SimulationReport, SimulationStepResult


MetricValue = float | int | str | None


class SimulationEvaluator:
    def build_report(
        self,
        *,
        persona_id: str,
        scenario_id: str,
        steps: list[SimulationStepResult],
        api_calls: int,
        api_successes: int,
        agent_triggers: int,
        memory_writes: int,
        mode: SimulationMode = "contract",
        runtime_metrics: dict[str, Any] | None = None,
        scenario_contract: dict | None = None,
    ) -> SimulationReport:
        runtime_metrics = runtime_metrics or {}
        failures = [failure for step in steps for failure in step.failures]
        assertion_total = sum(1 for step in steps for _ in step.failures) + len(
            [step for step in steps if step.status == "passed"]
        )
        assertion_passes = len([step for step in steps if step.status == "passed"])
        metrics = {
            "api_success_rate": api_successes / api_calls if api_calls else 1.0,
            "agent_trigger_count": agent_triggers,
            "memory_write_count": memory_writes,
            "assertion_pass_rate": assertion_passes / assertion_total if assertion_total else 1.0,
        }
        metric_groups = build_metric_groups(
            steps=steps,
            metrics=metrics,
            runtime_metrics=runtime_metrics,
            scenario_contract=scenario_contract or {},
        )
        return SimulationReport(
            persona=persona_id,
            scenario=scenario_id,
            mode=mode,
            status="passed" if not failures and all(step.status != "failed" for step in steps) else "failed",
            steps=steps,
            metrics=metrics,
            runtime_metrics=runtime_metrics,
            metric_groups=metric_groups,
            scenario_contract=scenario_contract,
            failures=failures,
        )


def build_metric_groups(
    *,
    steps: list[SimulationStepResult],
    metrics: dict[str, float | int],
    runtime_metrics: Mapping[str, Any],
    scenario_contract: Mapping[str, Any],
) -> dict[str, dict[str, MetricValue]]:
    event_types = _list_values(runtime_metrics.get("event_types"))
    tool_statuses = _list_values(runtime_metrics.get("tool_statuses"))
    tool_latencies = _number_list(runtime_metrics.get("tool_latencies_ms"))
    prompt_executions = runtime_metrics.get("prompt_executions")
    if not isinstance(prompt_executions, list):
        prompt_executions = []

    exercise_attempt_created_count = _count_step_outputs(steps, "attempt.attempt_id")
    grading_success_count = _count_matching_step_outputs(steps, "answer.grading_result.correct", True)
    mastery_deltas = _mastery_deltas(steps)
    memory_event_count = max(
        int(runtime_metrics.get("memory_event_count") or 0),
        event_types.count("memory_written"),
        _count_memory_updates(steps),
    )
    recommendation_generated_count = max(
        int(runtime_metrics.get("recommendation_generated_count") or 0),
        _recommendation_count(steps),
    )
    capability_click_count = int(runtime_metrics.get("capability_click_recorded_count") or 0)

    return {
        "runtime": {
            "episode_count": int(runtime_metrics.get("episode_count") or 0),
            "completed_episode_count": int(runtime_metrics.get("completed_episode_count") or 0),
            "failed_episode_count": int(runtime_metrics.get("failed_episode_count") or 0),
            "episode_completion_rate": _rate(
                int(runtime_metrics.get("completed_episode_count") or 0),
                int(runtime_metrics.get("episode_count") or 0),
            ),
            "verification_pass_count": int(runtime_metrics.get("verification_pass_count") or 0),
            "verification_fail_count": int(runtime_metrics.get("verification_fail_count") or 0),
            "verification_pass_rate": _rate(
                int(runtime_metrics.get("verification_pass_count") or 0),
                int(runtime_metrics.get("verification_pass_count") or 0)
                + int(runtime_metrics.get("verification_fail_count") or 0),
            ),
            "tool_success_rate": _tool_success_rate(tool_statuses),
            "avg_tool_latency_ms": _avg(tool_latencies),
            "p95_tool_latency_ms": _percentile(tool_latencies, 0.95),
        },
        "learning": {
            "exercise_attempt_created_count": exercise_attempt_created_count,
            "grading_success_count": grading_success_count,
            "grading_success_rate": _rate(grading_success_count, exercise_attempt_created_count),
            "mastery_update_count": max(event_types.count("mastery_updated"), _count_step_outputs(steps, "answer.mastery_update")),
            "mastery_delta_positive_count": sum(1 for value in mastery_deltas if value > 0),
            "mastery_delta_negative_count": sum(1 for value in mastery_deltas if value < 0),
            "mastery_delta_direction_correct_rate": _mastery_direction_rate(mastery_deltas),
            "review_schedule_created_count": event_types.count("review_scheduled"),
        },
        "memory": {
            "memory_write_count": metrics["memory_write_count"],
            "memory_event_count": memory_event_count,
            "expected_memory_event_coverage": _expected_event_coverage(
                event_types,
                scenario_contract,
                prefix="memory",
            ),
            "memory_evidence_ref_coverage": _memory_evidence_ref_coverage(steps),
            "memory_recall_count": int(runtime_metrics.get("memory_recall_count") or 0),
        },
        "recommendation": {
            "recommendation_generated_count": recommendation_generated_count,
            "recommendation_contains_expected_count": int(
                runtime_metrics.get("recommendation_contains_expected_count") or recommendation_generated_count
            ),
            "recommendation_relevance_pass_rate": _rate(
                int(runtime_metrics.get("recommendation_contains_expected_count") or recommendation_generated_count),
                recommendation_generated_count,
            ),
            "capability_click_recorded_count": capability_click_count,
        },
        "parser_rag": {
            "rag_retrieval_result_count": int(runtime_metrics.get("rag_retrieval_result_count") or 0),
            "rag_evidence_coverage": _none_if_missing(runtime_metrics.get("rag_evidence_coverage")),
            "source_page_coverage": _none_if_missing(runtime_metrics.get("source_page_coverage")),
            "parser_quality_score": _none_if_missing(runtime_metrics.get("parser_quality_score")),
        },
        "prompt_schema": {
            "prompt_execution_count": len(prompt_executions),
            "schema_validation_pass_count": _count_prompt_statuses(prompt_executions, {"passed", "repaired"}),
            "schema_validation_fail_count": _count_prompt_statuses(prompt_executions, {"failed"}),
            "schema_validation_pass_rate": _rate(
                _count_prompt_statuses(prompt_executions, {"passed", "repaired"}),
                len(prompt_executions),
            ),
            "json_repair_count": _count_prompt_flag(prompt_executions, "repair_used"),
            "fallback_used_count": _count_prompt_flag(prompt_executions, "fallback_used"),
            "prompt_hash_coverage": _coverage(prompt_executions, "prompt_hash"),
            "model_policy_coverage": _coverage(prompt_executions, "model_policy_snapshot"),
        },
    }


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


def _list_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _number_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if isinstance(item, int | float)]


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((len(ordered) - 1) * percentile)))
    return ordered[index]


def _tool_success_rate(statuses: list[str]) -> float | None:
    if not statuses:
        return None
    successes = sum(1 for status in statuses if status.casefold() in {"success", "passed", "completed"})
    return successes / len(statuses)


def _count_step_outputs(steps: list[SimulationStepResult], path: str) -> int:
    return sum(1 for step in steps if _lookup(step.output, path) is not None)


def _count_matching_step_outputs(
    steps: list[SimulationStepResult],
    path: str,
    expected: Any,
) -> int:
    return sum(1 for step in steps if _lookup(step.output, path) == expected)


def _count_memory_updates(steps: list[SimulationStepResult]) -> int:
    total = 0
    for step in steps:
        updates = _lookup(step.output, "answer.memory_updates")
        if isinstance(updates, list):
            total += len(updates)
    return total


def _recommendation_count(steps: list[SimulationStepResult]) -> int:
    total = 0
    for step in steps:
        recommendations = _lookup(step.output, "answer.next_capability_recommendations")
        if isinstance(recommendations, list):
            total += len(recommendations)
    return total


def _mastery_deltas(steps: list[SimulationStepResult]) -> list[float]:
    values: list[float] = []
    for step in steps:
        update = _lookup(step.output, "answer.mastery_update")
        if not isinstance(update, Mapping):
            continue
        for key in ("mastery_delta", "delta"):
            value = update.get(key)
            if isinstance(value, int | float):
                values.append(float(value))
                break
    return values


def _mastery_direction_rate(values: list[float]) -> float | None:
    if not values:
        return None
    positive = sum(1 for value in values if value >= 0)
    return positive / len(values)


def _expected_event_coverage(
    event_types: list[str],
    scenario_contract: Mapping[str, Any],
    *,
    prefix: str,
) -> float | None:
    expected = [
        event
        for event in scenario_contract.get("expected_events", [])
        if isinstance(event, str) and event.startswith(prefix)
    ]
    if not expected:
        return None
    covered = sum(1 for event in expected if event in event_types)
    return covered / len(expected)


def _memory_evidence_ref_coverage(steps: list[SimulationStepResult]) -> float | None:
    updates = []
    for step in steps:
        raw_updates = _lookup(step.output, "answer.memory_updates")
        if isinstance(raw_updates, list):
            updates.extend(item for item in raw_updates if isinstance(item, Mapping))
    if not updates:
        return None
    with_evidence = sum(1 for item in updates if item.get("evidence_refs"))
    return with_evidence / len(updates)


def _none_if_missing(value: Any) -> float | int | str | None:
    return value if isinstance(value, int | float | str) else None


def _count_prompt_statuses(prompt_executions: list[Any], statuses: set[str]) -> int:
    return sum(
        1
        for item in prompt_executions
        if isinstance(item, Mapping) and str(item.get("schema_validation_status")).casefold() in statuses
    )


def _count_prompt_flag(prompt_executions: list[Any], flag: str) -> int:
    return sum(1 for item in prompt_executions if isinstance(item, Mapping) and item.get(flag) is True)


def _coverage(items: list[Any], key: str) -> float | None:
    if not items:
        return None
    covered = sum(1 for item in items if isinstance(item, Mapping) and item.get(key))
    return covered / len(items)
