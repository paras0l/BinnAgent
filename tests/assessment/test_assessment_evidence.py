from src.adaptive.evidence import AssessmentEvidenceInput, evaluate_evidence


def _evidence(**overrides) -> AssessmentEvidenceInput:
    payload = {
        "knowledge_point_id": "grammar.article_usage",
        "item_id": "item-001",
        "outcome_score": 1.0,
        "evidence_ref": "attempt-001",
    }
    payload.update(overrides)
    return AssessmentEvidenceInput(**payload)


def test_assessment_evidence_is_eligible_for_state_update() -> None:
    decision = evaluate_evidence(_evidence())
    assert decision.accepted is True
    assert decision.updates_learning_state is True


def test_low_confidence_evidence_is_retained_without_state_update() -> None:
    decision = evaluate_evidence(_evidence(semantic_confidence=0.4))
    assert decision.accepted is True
    assert decision.updates_learning_state is False


def test_browsing_is_not_assessment_evidence() -> None:
    decision = evaluate_evidence(_evidence(interaction_type="browsing"))
    assert decision.accepted is False
    assert decision.updates_learning_state is False
