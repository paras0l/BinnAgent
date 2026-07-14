import uuid
from datetime import datetime, timedelta, timezone

from src.adaptive.correction import replay_evidence
from src.models.adaptive import AssessmentEvidence

T0 = datetime(2026, 7, 14, 10, tzinfo=timezone.utc)


def _record(*, outcome: float, created_at: datetime) -> AssessmentEvidence:
    record = AssessmentEvidence(
        learner_id=uuid.uuid4(),
        attempt_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        item_id="item",
        evidence_mode="recall",
        outcome_score=outcome,
        independent=True,
        hint_count=0,
        retry_count=0,
        response_time_ms=5000,
        error_tags=[],
        semantic_confidence=1.0,
        item_difficulty_prior=0.5,
        interaction_type="assessment",
        accepted=True,
        updates_learning_state=True,
        decision_reason="assessment_evidence_accepted",
        evidence_ref=str(uuid.uuid4()),
    )
    record.id = uuid.uuid4()
    record.created_at = created_at
    return record


def test_replay_rebuilds_state_from_remaining_evidence_in_time_order() -> None:
    correct = _record(outcome=1.0, created_at=T0)
    incorrect = _record(outcome=0.0, created_at=T0 + timedelta(days=2))

    mastery_after_correct, _, correct_schedule = replay_evidence([correct])
    mastery_after_both, _, both_schedule = replay_evidence([correct, incorrect])

    assert mastery_after_both < mastery_after_correct
    assert correct_schedule is not None
    assert both_schedule is not None
    assert both_schedule.review_count == 2


def test_replay_with_no_evidence_clears_derived_state() -> None:
    mastery, predicted, schedule = replay_evidence([])
    assert mastery == 0.0
    assert predicted is None
    assert schedule is None
