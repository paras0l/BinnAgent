from datetime import datetime, timedelta, timezone
import uuid

import pytest

from src.api.grammar import _dimension_payload, _learning_status
from src.models.adaptive import AssessmentEvidence
from src.models.knowledge import LearnerKnowledgeState


def _evidence(*, mode: str, score: float, confidence: float = 1.0) -> AssessmentEvidence:
    return AssessmentEvidence(
        learner_id=uuid.uuid4(),
        attempt_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        item_id="item-1",
        evidence_mode=mode,
        outcome_score=score,
        independent=True,
        hint_count=0,
        retry_count=0,
        error_tags=[],
        semantic_confidence=confidence,
        item_difficulty_prior=0.4,
        interaction_type="assessment",
        accepted=True,
        updates_learning_state=True,
        decision_reason="accepted",
        evidence_ref="attempt:test",
    )


def _state(score: float, *, next_review_at=None) -> LearnerKnowledgeState:
    return LearnerKnowledgeState(
        learner_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        status="learning",
        mastery_score=score,
        confidence=0.5,
        ability=score,
        exposure_count=2,
        correct_count=1,
        next_review_at=next_review_at,
        evidence_summary={},
    )


def test_dimension_payload_keeps_modes_separate():
    dimensions = _dimension_payload([
        _evidence(mode="recognition", score=1.0),
        _evidence(mode="production", score=0.25),
    ])

    by_mode = {item.mode: item for item in dimensions}
    assert by_mode["recognition"].score == 1.0
    assert by_mode["recall"].evidence_count == 0
    assert by_mode["production"].score == 0.25


@pytest.mark.parametrize(
    ("state", "evidence", "retrievability", "expected"),
    [
        (None, [], None, "no_evidence"),
        (_state(0.85), [_evidence(mode="recall", score=1)], 0.9, "stable"),
        (_state(0.5), [_evidence(mode="recall", score=1)], 0.9, "forming"),
        (_state(0.8), [_evidence(mode="recall", score=1)], 0.4, "review"),
        (_state(0.4), [_evidence(mode="recall", score=0.2), _evidence(mode="production", score=0.1)], 0.9, "repeated_failure"),
    ],
)
def test_learning_status_uses_evidence_not_completion(state, evidence, retrievability, expected):
    assert _learning_status(state, evidence, retrievability, datetime.now(timezone.utc)) == expected


def test_overdue_state_requires_review():
    now = datetime.now(timezone.utc)
    state = _state(0.9, next_review_at=now - timedelta(minutes=1))
    assert _learning_status(state, [_evidence(mode="recall", score=1)], 0.9, now) == "review"
