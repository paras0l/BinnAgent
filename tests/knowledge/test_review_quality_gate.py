import uuid

from src.knowledge.review_queue import apply_quality_gate, queue_summary
from src.models.knowledge import KnowledgeSource, ParserReviewItem


def _healthy_report() -> dict:
    return {
        "unit_count": 12,
        "expected_unit_count": 12,
        "unit_title_match_rate": 1.0,
        "unit_order_valid": True,
        "section_coverage_rate": 1.0,
        "core_vocabulary_hit_rate": 1.0,
        "low_confidence_vocabulary_ratio": 0.0,
        "dirty_token_entry_count": 0,
        "source_page_coverage_rate": 1.0,
        "evidence_ref_coverage_rate": 1.0,
        "rag_chunk_count": 24,
        "rag_page_coverage_rate": 1.0,
        "chunk_avg_size": 360,
        "warnings": [],
    }


def _source() -> KnowledgeSource:
    source = KnowledgeSource(
        title="book",
        filename="book.pdf",
        grade="grade-7",
        status="review_required",
        sha256="a" * 64,
        file_size=10,
        unit_count=12,
        knowledge_count=20,
        metadata_={"parser_report": _healthy_report()},
    )
    source.id = uuid.uuid4()
    return source


def _item(source_id: uuid.UUID, *, severity: str, decision: str = "pending") -> ParserReviewItem:
    item = ParserReviewItem(
        source_id=source_id,
        target_type="source",
        issue_type="quality_gate_blocker",
        severity=severity,
        decision=decision,
    )
    item.id = uuid.uuid4()
    return item


def test_pending_blocker_prevents_published_status() -> None:
    source = _source()

    apply_quality_gate(source, summary=queue_summary([_item(source.id, severity="blocker")]))

    assert source.status == "blocked"
    assert source.metadata_["pending_review_count"] == 1
    assert source.metadata_["pending_blocker_count"] == 1
    assert "Parser review blockers are still pending." in source.metadata_["blocking_reasons"]


def test_source_publishes_when_pending_review_queue_is_empty_and_report_is_healthy() -> None:
    source = _source()

    apply_quality_gate(
        source,
        summary=queue_summary([_item(source.id, severity="blocker", decision="confirmed")]),
    )

    assert source.status == "published"
    assert source.metadata_["pending_review_count"] == 0
    assert source.metadata_["pending_blocker_count"] == 0
