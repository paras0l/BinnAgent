from typing import Any

from src.evidence.types import EvidenceRef
from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView, LearningEventView
from src.verification.types import VerificationCheck


def check_event_exists(
    episode_trace: EpisodeTraceView,
    event_type: str,
    *,
    name: str | None = None,
    severity: str = "warning",
    check_type: str = "event",
    message: str | None = None,
) -> VerificationCheck:
    matching = [event for event in episode_trace.events if event.event_type == event_type]
    refs = _collect_event_evidence(matching)
    return VerificationCheck(
        name=name or event_type,
        check_type=check_type,
        passed=bool(matching),
        expected=f"event:{event_type}",
        actual=[event.event_type for event in matching],
        severity=severity,
        source_event_type=event_type,
        evidence_refs=refs,
        message=message
        or (
            f"Found {len(matching)} event(s) for {event_type}."
            if matching
            else f"Missing event {event_type}."
        ),
    )


def check_tool_call_success(
    episode_trace: EpisodeTraceView,
    tool_name: str,
    *,
    severity: str = "warning",
) -> VerificationCheck:
    matching = [tool for tool in episode_trace.tool_calls if tool.tool_name == tool_name]
    successful = [tool for tool in matching if tool.status == "success"]
    return VerificationCheck(
        name=f"tool:{tool_name}",
        check_type="tool",
        passed=bool(successful),
        expected="success",
        actual=[{"tool_name": tool.tool_name, "status": tool.status} for tool in matching],
        severity=severity,
        source_tool_name=tool_name,
        message=(
            f"Found successful tool call {tool_name}."
            if successful
            else f"Missing successful tool call {tool_name}."
        ),
    )


def check_payload_field_exists(
    event: LearningEventView,
    field: str,
    *,
    severity: str = "warning",
) -> VerificationCheck:
    exists = field in (event.payload or {})
    return VerificationCheck(
        name=f"{event.event_type}.{field}",
        check_type="schema",
        passed=exists,
        expected=f"payload field {field}",
        actual=event.payload.get(field) if event.payload else None,
        severity=severity,
        source_event_type=event.event_type,
        evidence_refs=_collect_event_evidence([event]),
        message=(
            f"Payload field {field} exists on {event.event_type}."
            if exists
            else f"Missing payload field {field} on {event.event_type}."
        ),
    )


def check_score_range(score: float | int | None, *, severity: str = "critical") -> VerificationCheck:
    passed = isinstance(score, (float, int)) and 0.0 <= float(score) <= 1.0
    return VerificationCheck(
        name="score_range",
        check_type="business_rule",
        passed=passed,
        expected="0 <= score <= 1",
        actual=score,
        severity=severity,
        message="Score is within 0-1." if passed else "Score is outside 0-1.",
    )


def check_evidence_non_empty(
    evidence_refs: list[EvidenceRef],
    *,
    name: str = "evidence_refs_present",
    severity: str = "info",
) -> VerificationCheck:
    return VerificationCheck(
        name=name,
        check_type="evidence",
        passed=bool(evidence_refs),
        expected="at least one evidence ref",
        actual=len(evidence_refs),
        severity=severity,
        evidence_refs=evidence_refs,
        message=(
            f"Found {len(evidence_refs)} evidence ref(s)."
            if evidence_refs
            else "No evidence_refs were attached."
        ),
    )


def check_episode_completed(episode: AgentEpisodeView, *, severity: str = "warning") -> VerificationCheck:
    passed = episode.status == "completed"
    return VerificationCheck(
        name="episode_completed",
        check_type="deterministic",
        passed=passed,
        expected="completed",
        actual=episode.status,
        severity=severity,
        message="Episode status is completed." if passed else "Episode is not completed.",
    )


def _collect_event_evidence(events: list[LearningEventView]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for event in events:
        raw_refs = (event.payload or {}).get("evidence_refs") or []
        for raw_ref in raw_refs:
            parsed = parse_evidence_ref(raw_ref)
            if parsed is not None:
                refs.append(parsed)
    return refs


def collect_trace_evidence(episode_trace: EpisodeTraceView) -> list[EvidenceRef]:
    return _collect_event_evidence(list(episode_trace.events))


def parse_evidence_ref(raw_ref: Any) -> EvidenceRef | None:
    if isinstance(raw_ref, EvidenceRef):
        return raw_ref
    if not isinstance(raw_ref, dict):
        return None
    normalized = dict(raw_ref)
    if "evidence_type" not in normalized and "type" in normalized:
        normalized["evidence_type"] = normalized["type"]
    if "evidence_id" not in normalized and "id" in normalized:
        normalized["evidence_id"] = normalized["id"]
    if "evidence_type" not in normalized or "evidence_id" not in normalized:
        return None
    metadata = normalized.get("metadata")
    normalized["metadata"] = metadata if isinstance(metadata, dict) else {}
    for key in ("type", "id", "source"):
        if key in raw_ref and key not in normalized["metadata"]:
            normalized["metadata"][key] = raw_ref[key]
    try:
        return EvidenceRef(**normalized)
    except ValueError:
        return None


def value_in_score_range(value: Any) -> bool:
    return isinstance(value, (float, int)) and 0.0 <= float(value) <= 1.0
