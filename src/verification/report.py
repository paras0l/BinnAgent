from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.types import EvidenceRef
from src.runtime.episode import EpisodeRuntime
from src.runtime.schemas import EpisodeTraceView
from src.verification.checks import (
    check_episode_completed,
    check_event_exists,
    check_evidence_non_empty,
    check_score_range,
    check_tool_call_success,
    collect_trace_evidence,
    value_in_score_range,
)
from src.verification.types import VerificationCheck, VerificationReport


class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_episode(self, episode_id: str) -> VerificationReport:
        trace = await EpisodeRuntime(self.db).get_episode_trace(episode_id)
        return build_verification_report(trace)


def build_verification_report(trace: EpisodeTraceView) -> VerificationReport:
    task_spec = trace.episode.task_spec or {}
    policy = task_spec.get("verification_policy") or {}
    required_checks = list(policy.get("required_checks") or [])
    if not required_checks:
        required_checks = ["episode_started", "exercise_answered", "exercise_graded"]
    if policy.get("require_evidence", False) and "evidence_non_empty" not in required_checks:
        required_checks.append("evidence_non_empty")

    checks = [_run_check(name, trace) for name in required_checks]
    failed = [check for check in checks if not check.passed]
    status = "passed" if not failed else "failed"
    return VerificationReport(
        episode_id=trace.episode.id,
        task_id=task_spec.get("task_id"),
        status=status,
        checks=checks,
        failed_reason="; ".join(check.message or check.name for check in failed) or None,
        generated_at=datetime.now(timezone.utc),
        metadata={
            "required_checks": required_checks,
            "source": task_spec.get("source"),
            "task_type": task_spec.get("task_type"),
        },
    )


async def verify_knowledge_exercise_episode(
    db: AsyncSession,
    episode_id: str,
    trace: EpisodeTraceView | None = None,
) -> dict[str, Any]:
    report = (
        build_verification_report(trace)
        if trace is not None
        else await VerificationService(db).verify_episode(episode_id)
    )
    return report.model_dump(mode="json")


def _run_check(name: str, trace: EpisodeTraceView) -> VerificationCheck:
    normalized = name.strip()
    aliases = {
        "memory_event_written": "memory_written",
        "grading_result_exists": "exercise_graded",
    }
    normalized = aliases.get(normalized, normalized)

    if normalized in {
        "episode_started",
        "exercise_answered",
        "exercise_graded",
        "memory_written",
        "review_scheduled",
    }:
        return check_event_exists(trace, normalized)
    if normalized == "exercise_attempt_saved":
        return _check_exercise_attempt_saved(trace)
    if normalized == "mastery_update_valid":
        return _check_mastery_update_valid(trace)
    if normalized == "evidence_non_empty":
        return check_evidence_non_empty(collect_trace_evidence(trace))
    if normalized == "episode_completed":
        return check_episode_completed(trace.episode)
    if normalized.startswith("tool:"):
        return check_tool_call_success(trace, normalized.removeprefix("tool:"))
    return VerificationCheck(
        name=normalized,
        check_type="deterministic",
        passed=False,
        expected="known check",
        actual=None,
        message=f"Unsupported verification check {normalized}",
    )


def _check_exercise_attempt_saved(trace: EpisodeTraceView) -> VerificationCheck:
    events = [event for event in trace.events if event.event_type == "exercise_answered"]
    attempt_ids = [
        event.payload.get("attempt_id")
        for event in events
        if event.payload and event.payload.get("attempt_id")
    ]
    return VerificationCheck(
        name="exercise_attempt_saved",
        check_type="business_rule",
        passed=bool(attempt_ids),
        expected="exercise_answered payload.attempt_id",
        actual=attempt_ids,
        evidence_refs=_event_refs(events),
        message=None if attempt_ids else "No saved exercise attempt id found",
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
    check = check_score_range(scores[0] if scores else None)
    return VerificationCheck(
        name="mastery_update_valid",
        check_type="business_rule",
        passed=passed,
        expected="mastery_updated event with score in 0-1",
        actual=scores,
        evidence_refs=_event_refs(events),
        message=None if passed else check.message or "Missing valid mastery update",
    )


def _event_refs(events) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for event in events:
        raw_refs = (event.payload or {}).get("evidence_refs") or []
        refs.extend(EvidenceRef(**item) for item in raw_refs if isinstance(item, dict))
    return refs
