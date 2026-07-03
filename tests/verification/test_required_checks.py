import uuid
from datetime import datetime, timezone

from src.runtime.events import LearningEventView
from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView
from src.verification.report import build_verification_report


def _trace(
    events: list[LearningEventView],
    *,
    task_spec: dict | None = None,
    status: str = "running",
) -> EpisodeTraceView:
    now = datetime.now(timezone.utc)
    return EpisodeTraceView(
        episode=AgentEpisodeView(
            id=str(uuid.uuid4()),
            learner_id=str(uuid.uuid4()),
            source="textbook_guided",
            entrypoint="test",
            status=status,
            task_spec=task_spec or {"task_id": "task-1"},
            started_at=now,
            completed_at=now if status == "completed" else None,
            created_at=now,
            updated_at=now,
        ),
        events=events,
        tool_calls=[],
    )


def _event(event_type: str, payload: dict | None = None) -> LearningEventView:
    return LearningEventView(
        id=str(uuid.uuid4()),
        episode_id=str(uuid.uuid4()),
        learner_id=str(uuid.uuid4()),
        event_type=event_type,
        source_module="daily_lesson",
        target_type="knowledge_point",
        target_id=str(uuid.uuid4()),
        payload=payload or {},
        occurred_at=datetime.now(timezone.utc),
    )


def _task_spec(required_checks: list[str], *, require_evidence: bool = False) -> dict:
    return {
        "task_id": "task-1",
        "task_type": "practice_knowledge_point",
        "source": "recommendation",
        "verification_policy": {
            "required_checks": required_checks,
            "require_evidence": require_evidence,
        },
    }


def test_required_checks_empty_uses_default_checks() -> None:
    report = build_verification_report(
        _trace(
            [
                _event("episode_started"),
                _event("exercise_answered"),
                _event("exercise_graded"),
            ],
            task_spec=_task_spec([]),
        )
    )

    assert report.status == "passed"
    assert report.required_checks == ["episode_started", "exercise_answered", "exercise_graded"]


def test_required_mastery_updated_missing_fails_critically() -> None:
    report = build_verification_report(
        _trace([_event("exercise_graded")], task_spec=_task_spec(["mastery_updated"]))
    )

    assert report.status == "failed"
    assert report.critical_failed_count == 1
    assert report.checks[0].name == "mastery_updated"
    assert report.checks[0].severity == "critical"


def test_missing_memory_event_written_is_warning() -> None:
    report = build_verification_report(
        _trace([_event("exercise_graded")], task_spec=_task_spec(["memory_event_written"]))
    )

    assert report.status == "warning"
    assert report.warning_count == 1
    assert report.critical_failed_count == 0


def test_evidence_refs_are_aggregated_from_event_payloads() -> None:
    evidence_ref = {
        "evidence_type": "exercise_attempt",
        "evidence_id": str(uuid.uuid4()),
        "reason": "graded answer",
    }
    report = build_verification_report(
        _trace(
            [_event("exercise_graded", {"evidence_refs": [evidence_ref]})],
            task_spec=_task_spec(["exercise_graded"], require_evidence=True),
        )
    )

    assert report.status == "passed"
    assert report.evidence_ref_count == 1
    assert report.checks[-1].name == "evidence_refs_present"
    assert report.checks[-1].passed is True


def test_prompt_schema_valid_without_records_warns_not_crashes() -> None:
    report = build_verification_report(
        _trace([], task_spec=_task_spec(["prompt_schema_valid"]))
    )

    assert report.status == "warning"
    assert report.checks[0].name == "prompt_schema_valid"
    assert report.checks[0].passed is False
