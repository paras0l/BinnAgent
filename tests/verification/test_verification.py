import uuid
from datetime import datetime, timezone

from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView
from src.runtime.events import LearningEventView
from src.verification.checks import check_event_exists
from src.verification.report import _run_check


def _trace(events: list[LearningEventView], *, status: str = "running") -> EpisodeTraceView:
    now = datetime.now(timezone.utc)
    return EpisodeTraceView(
        episode=AgentEpisodeView(
            id=str(uuid.uuid4()),
            learner_id=str(uuid.uuid4()),
            source="textbook_guided",
            entrypoint="test",
            status=status,
            task_spec={"task_id": "task-1"},
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
        source_module="knowledge",
        target_type="knowledge_point",
        target_id=str(uuid.uuid4()),
        payload=payload or {},
        occurred_at=datetime.now(timezone.utc),
    )


def test_missing_exercise_graded_event_fails():
    check = check_event_exists(_trace([_event("exercise_answered")]), "exercise_graded")

    assert check.passed is False


def test_complete_event_chain_passes_required_event_checks():
    trace = _trace(
        [
            _event("episode_started"),
            _event("exercise_answered", {"attempt_id": str(uuid.uuid4())}),
            _event("exercise_graded", {"score": 1.0}),
        ],
        status="completed",
    )

    assert _run_check("episode_started", trace).passed is True
    assert _run_check("exercise_answered", trace).passed is True
    assert _run_check("exercise_graded", trace).passed is True
    assert _run_check("episode_completed", trace).passed is True


def test_mastery_score_out_of_range_fails():
    trace = _trace([_event("mastery_updated", {"new_score": 1.2})])

    assert _run_check("mastery_update_valid", trace).passed is False


def test_evidence_required_but_empty_fails():
    assert _run_check("evidence_non_empty", _trace([_event("exercise_graded")])).passed is False
