from typing import Any

from src.evidence.types import EvidenceRef
from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView, LearningEventView
from src.verification.types import VerificationCheck


def check_event_exists(episode_trace: EpisodeTraceView, event_type: str) -> VerificationCheck:
    matching = [event for event in episode_trace.events if event.event_type == event_type]
    return VerificationCheck(
        name=event_type,
        check_type="deterministic",
        passed=bool(matching),
        expected=f"event:{event_type}",
        actual=[event.event_type for event in matching],
        evidence_refs=_collect_event_evidence(matching),
        message=None if matching else f"Missing event {event_type}",
    )


def check_tool_call_success(episode_trace: EpisodeTraceView, tool_name: str) -> VerificationCheck:
    matching = [tool for tool in episode_trace.tool_calls if tool.tool_name == tool_name]
    successful = [tool for tool in matching if tool.status == "success"]
    return VerificationCheck(
        name=f"tool:{tool_name}",
        check_type="deterministic",
        passed=bool(successful),
        expected="success",
        actual=[{"tool_name": tool.tool_name, "status": tool.status} for tool in matching],
        message=None if successful else f"Missing successful tool call {tool_name}",
    )


def check_payload_field_exists(event: LearningEventView, field: str) -> VerificationCheck:
    exists = field in (event.payload or {})
    return VerificationCheck(
        name=f"{event.event_type}.{field}",
        check_type="schema",
        passed=exists,
        expected=f"payload field {field}",
        actual=event.payload.get(field) if event.payload else None,
        evidence_refs=_collect_event_evidence([event]),
        message=None if exists else f"Missing payload field {field}",
    )


def check_score_range(score: float | int | None) -> VerificationCheck:
    passed = isinstance(score, (float, int)) and 0.0 <= float(score) <= 1.0
    return VerificationCheck(
        name="score_range",
        check_type="business_rule",
        passed=passed,
        expected="0 <= score <= 1",
        actual=score,
        message=None if passed else "Score is outside 0-1",
    )


def check_evidence_non_empty(evidence_refs: list[EvidenceRef]) -> VerificationCheck:
    return VerificationCheck(
        name="evidence_non_empty",
        check_type="business_rule",
        passed=bool(evidence_refs),
        expected="at least one evidence ref",
        actual=len(evidence_refs),
        evidence_refs=evidence_refs,
        message=None if evidence_refs else "No evidence_refs were attached",
    )


def check_episode_completed(episode: AgentEpisodeView) -> VerificationCheck:
    passed = episode.status == "completed"
    return VerificationCheck(
        name="episode_completed",
        check_type="deterministic",
        passed=passed,
        expected="completed",
        actual=episode.status,
        message=None if passed else "Episode is not completed",
    )


def _collect_event_evidence(events: list[LearningEventView]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for event in events:
        raw_refs = (event.payload or {}).get("evidence_refs") or []
        for raw_ref in raw_refs:
            if isinstance(raw_ref, EvidenceRef):
                refs.append(raw_ref)
            elif isinstance(raw_ref, dict):
                refs.append(EvidenceRef(**raw_ref))
    return refs


def collect_trace_evidence(episode_trace: EpisodeTraceView) -> list[EvidenceRef]:
    return _collect_event_evidence(list(episode_trace.events))


def value_in_score_range(value: Any) -> bool:
    return isinstance(value, (float, int)) and 0.0 <= float(value) <= 1.0
