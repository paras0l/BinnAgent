import uuid

from src.models.knowledge import ParserReviewItem


def test_parser_review_item_model_carries_target_and_decision_metadata() -> None:
    source_id = uuid.uuid4()
    parser_run_id = uuid.uuid4()
    target_id = uuid.uuid4()

    item = ParserReviewItem(
        source_id=source_id,
        parser_run_id=parser_run_id,
        target_type="knowledge_point",
        target_id=target_id,
        issue_type="low_confidence",
        severity="warning",
        evidence_snapshot={"raw_line": "hello p.1", "confidence": 0.62},
        suggested_fix={"action": "confirm_or_update"},
        decision="pending",
    )

    assert item.source_id == source_id
    assert item.parser_run_id == parser_run_id
    assert item.target_type == "knowledge_point"
    assert item.target_id == target_id
    assert item.decision == "pending"
