from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.evidence.types import EvidenceRef
from src.runtime.schemas import EpisodeTraceView
from src.verification.checks import (
    check_event_exists,
    check_evidence_non_empty,
    check_score_range,
    check_tool_call_success,
    collect_trace_evidence,
    parse_evidence_ref,
    value_in_score_range,
)
from src.verification.types import VerificationCheck


DEFAULT_REQUIRED_CHECKS = [
    "episode_started",
    "exercise_answered",
    "exercise_graded",
]

CANONICAL_REQUIRED_CHECKS = [
    "task_prepared",
    "learner_answer_received",
    "exercise_attempt_created",
    "exercise_graded",
    "mastery_updated",
    "memory_event_written",
    "review_scheduled",
    "next_action_recommended",
    "episode_completed",
    "tool_calls_successful",
    "evidence_refs_present",
    "prompt_schema_valid",
]

ALIASES = {
    "answer_received": "learner_answer_received",
    "grading_result_exists": "exercise_graded",
    "memory_written": "memory_event_written",
    "memory_event_written": "memory_event_written",
    "evidence_non_empty": "evidence_refs_present",
    "review_items_prepared": "review_scheduled",
}

CRITICAL_CHECKS = {
    "learner_answer_received",
    "exercise_attempt_created",
    "exercise_attempt_saved",
    "exercise_graded",
    "mastery_updated",
    "mastery_update_valid",
}

WARNING_CHECKS = {
    "episode_started",
    "exercise_answered",
    "task_prepared",
    "memory_event_written",
    "review_scheduled",
    "next_action_recommended",
    "episode_completed",
    "tool_calls_successful",
    "prompt_schema_valid",
}

INFO_CHECKS = {"evidence_refs_present"}

EVENT_CHECKS = {
    "episode_started": "episode_started",
    "exercise_answered": "exercise_answered",
    "task_prepared": "task_prepared",
    "learner_answer_received": "learner_answer_received",
    "exercise_attempt_created": "exercise_attempt_created",
    "exercise_graded": "exercise_graded",
    "mastery_updated": "mastery_updated",
    "memory_event_written": "memory_written",
    "review_scheduled": "review_scheduled",
}


def checks_from_policy(task_spec: dict[str, Any]) -> list[str]:
    policy = task_spec.get("verification_policy") if isinstance(task_spec, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    checks = [str(item).strip() for item in (policy.get("required_checks") or []) if str(item).strip()]
    if not checks:
        checks = list(DEFAULT_REQUIRED_CHECKS)
    normalized = {_normalize(check) for check in checks}
    if policy.get("require_evidence", False) and "evidence_refs_present" not in normalized:
        checks.append("evidence_refs_present")
    return checks


def run_required_checks(trace: EpisodeTraceView, required_checks: Iterable[str]) -> list[VerificationCheck]:
    return [_run_check(name, trace) for name in required_checks]


def verification_status(checks: list[VerificationCheck]) -> str:
    if any(not check.passed and check.severity == "critical" for check in checks):
        return "failed"
    if any(not check.passed and check.severity == "warning" for check in checks):
        return "warning"
    return "passed"


def _run_check(name: str, trace: EpisodeTraceView) -> VerificationCheck:
    normalized = _normalize(name)
    if normalized == "episode_completed":
        return _check_episode_completed(trace)
    if normalized in EVENT_CHECKS:
        return _check_named_event(trace, normalized, EVENT_CHECKS[normalized])
    if normalized == "exercise_attempt_saved":
        return _check_exercise_attempt_saved(trace)
    if normalized == "mastery_update_valid":
        return _check_mastery_update_valid(trace)
    if normalized == "next_action_recommended":
        return _check_next_action_recommended(trace)
    if normalized == "tool_calls_successful":
        return _check_tool_calls_successful(trace)
    if normalized == "evidence_refs_present":
        return check_evidence_non_empty(
            collect_trace_evidence(trace),
            name=normalized,
            severity=_severity(normalized),
        )
    if normalized == "prompt_schema_valid":
        return _check_prompt_schema_valid(trace)
    if normalized.startswith("tool:"):
        return check_tool_call_success(
            trace,
            normalized.removeprefix("tool:"),
            severity=_severity(normalized),
        )
    return VerificationCheck(
        name=normalized,
        check_type="schema",
        passed=False,
        severity="critical",
        expected="supported verification check",
        actual=None,
        message=f"Unsupported verification check {normalized}.",
    )


def _normalize(name: str) -> str:
    stripped = name.strip()
    return ALIASES.get(stripped, stripped)


def _severity(name: str) -> str:
    if name in CRITICAL_CHECKS:
        return "critical"
    if name in INFO_CHECKS:
        return "info"
    if name in WARNING_CHECKS or name.startswith("tool:"):
        return "warning"
    return "warning"


def _check_named_event(
    trace: EpisodeTraceView,
    check_name: str,
    event_type: str,
) -> VerificationCheck:
    return check_event_exists(
        trace,
        event_type,
        name=check_name,
        severity=_severity(check_name),
        check_type="event",
    )


def _check_mastery_update_valid(trace: EpisodeTraceView) -> VerificationCheck:
    events = [event for event in trace.events if event.event_type == "mastery_updated"]
    scores: list[Any] = []
    for event in events:
        payload = event.payload or {}
        for field in ("new_score", "mastery_after", "score"):
            if field in payload:
                scores.append(payload[field])
                break
    passed = bool(scores) and all(value_in_score_range(score) for score in scores)
    score_check = check_score_range(scores[0] if scores else None, severity="critical")
    return VerificationCheck(
        name="mastery_update_valid",
        check_type="business_rule",
        passed=passed,
        severity="critical",
        expected="mastery_updated event with score in 0-1",
        actual=scores,
        source_node="update_mastery",
        source_event_type="mastery_updated",
        evidence_refs=_event_refs(events),
        message=(
            f"Found {len(scores)} valid mastery score(s)."
            if passed
            else score_check.message or "Missing valid mastery update."
        ),
    )


def _check_exercise_attempt_saved(trace: EpisodeTraceView) -> VerificationCheck:
    events = [
        event
        for event in trace.events
        if event.event_type in {"exercise_attempt_created", "exercise_answered"}
    ]
    attempt_ids = [
        event.payload.get("attempt_id")
        for event in events
        if event.payload and event.payload.get("attempt_id")
    ]
    return VerificationCheck(
        name="exercise_attempt_saved",
        check_type="business_rule",
        passed=bool(attempt_ids),
        severity="critical",
        expected="exercise_attempt_created or exercise_answered payload.attempt_id",
        actual=attempt_ids,
        source_node="grade_attempt",
        source_event_type=events[0].event_type if events else None,
        evidence_refs=_event_refs(events),
        message=(
            f"Found saved exercise attempt id(s): {', '.join(str(item) for item in attempt_ids)}."
            if attempt_ids
            else "No saved exercise attempt id found."
        ),
    )


def _check_episode_completed(trace: EpisodeTraceView) -> VerificationCheck:
    events = [event for event in trace.events if event.event_type == "episode_completed"]
    status_completed = trace.episode.status in {"completed", "completed_with_warnings"}
    passed = bool(events) or status_completed
    return VerificationCheck(
        name="episode_completed",
        check_type="event",
        passed=passed,
        severity="warning",
        expected="episode_completed event or completed episode status",
        actual={
            "event_count": len(events),
            "episode_status": trace.episode.status,
        },
        source_event_type="episode_completed" if events else None,
        evidence_refs=_event_refs(events),
        message=(
            "Episode completion is recorded."
            if passed
            else "Missing episode_completed event and completed status."
        ),
    )


def _check_next_action_recommended(trace: EpisodeTraceView) -> VerificationCheck:
    events = [
        event
        for event in trace.events
        if event.event_type in {"next_action_recommended", "explore_capability_recommended"}
    ]
    return VerificationCheck(
        name="next_action_recommended",
        check_type="business_rule",
        passed=bool(events),
        severity="warning",
        expected="next_action_recommended or explore_capability_recommended event",
        actual=[event.event_type for event in events],
        source_node="recommend_learning_action",
        source_event_type=events[0].event_type if events else None,
        evidence_refs=_event_refs(events),
        message=(
            f"Found {len(events)} next action recommendation event(s)."
            if events
            else "No next action recommendation event found."
        ),
    )


def _check_tool_calls_successful(trace: EpisodeTraceView) -> VerificationCheck:
    failed = [
        {"tool_name": tool.tool_name, "status": tool.status, "error": tool.error}
        for tool in trace.tool_calls
        if tool.status != "success"
    ]
    passed = bool(trace.tool_calls) and not failed
    return VerificationCheck(
        name="tool_calls_successful",
        check_type="tool",
        passed=passed,
        severity="warning",
        expected="all recorded tool calls have status=success",
        actual={
            "tool_call_count": len(trace.tool_calls),
            "failed": failed,
        },
        message=(
            f"All {len(trace.tool_calls)} recorded tool call(s) succeeded."
            if passed
            else "No tool calls were recorded." if not trace.tool_calls else "One or more tool calls failed."
        ),
    )


def _check_prompt_schema_valid(trace: EpisodeTraceView) -> VerificationCheck:
    prompt_executions = getattr(trace, "prompt_executions", []) or []
    invalid = [
        {
            "prompt_id": item.prompt_id,
            "schema_validation_status": item.schema_validation_status,
            "repair_used": item.repair_used,
            "fallback_used": item.fallback_used,
        }
        for item in prompt_executions
        if item.schema_validation_status not in {"valid", "passed", "repaired", "success"}
    ]
    passed = bool(prompt_executions) and not invalid
    return VerificationCheck(
        name="prompt_schema_valid",
        check_type="schema",
        passed=passed,
        severity="warning",
        expected="prompt executions schema_validation_status in valid/passed/repaired/success",
        actual={
            "prompt_execution_count": len(prompt_executions),
            "invalid": invalid,
        },
        source_event_type="prompt_execution",
        message=(
            f"All {len(prompt_executions)} prompt execution schema checks passed."
            if passed
            else "No prompt executions were recorded for this episode."
            if not prompt_executions
            else "One or more prompt executions failed schema validation."
        ),
    )


def _event_refs(events) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for event in events:
        raw_refs = (event.payload or {}).get("evidence_refs") or []
        for raw_ref in raw_refs:
            parsed = parse_evidence_ref(raw_ref)
            if parsed is not None:
                refs.append(parsed)
    return refs
