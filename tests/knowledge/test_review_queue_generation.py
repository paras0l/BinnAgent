import uuid

from src.knowledge.review_queue import build_parser_review_items
from src.models.knowledge import KnowledgePoint


def _point(
    *,
    source_id: uuid.UUID,
    title: str,
    source_page: str = "P.1",
    content: dict | None = None,
) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=uuid.uuid4(),
        canonical_key=f"vocabulary.{title}.{uuid.uuid4()}",
        type="vocabulary",
        title=title,
        summary=f"{title} summary",
        source_page=source_page,
        status="draft",
        content=content or {},
    )
    point.id = uuid.uuid4()
    return point


def test_review_queue_generation_covers_parser_issues_and_dedupes_per_run() -> None:
    source_id = uuid.uuid4()
    parser_run_id = uuid.uuid4()
    points = [
        _point(
            source_id=source_id,
            title="hello",
            content={
                "requires_review": True,
                "confidence": 0.62,
                "raw_line": "hello Page PB p.1",
                "origin": "unit_wordlist_sequence_parser",
            },
        ),
        _point(
            source_id=source_id,
            title="hello",
            source_page="",
            content={"confidence": 0.95, "warnings": ["schema invalid shape"]},
        ),
    ]
    report = {
        "dirty_tokens": ["Page PB"],
        "core_vocabulary_hit_rate": 0.2,
        "source_page_coverage_rate": 0.3,
        "evidence_ref_coverage_rate": 0.4,
        "rag_page_coverage_rate": 0.4,
    }
    quality_score = {
        "status": "blocked",
        "blocking_reasons": ["Core vocabulary hit rate is extremely low."],
    }

    items = build_parser_review_items(
        source_id=source_id,
        parser_run_id=parser_run_id,
        knowledge_points=points,
        report=report,
        quality_score=quality_score,
    )
    repeated = build_parser_review_items(
        source_id=source_id,
        parser_run_id=parser_run_id,
        knowledge_points=points,
        report=report,
        quality_score=quality_score,
    )

    issue_types = {item.issue_type for item in items}
    assert {
        "low_confidence",
        "dirty_token",
        "missing_source_page",
        "missing_evidence",
        "duplicate",
        "schema_invalid",
        "coverage_gap",
        "quality_gate_blocker",
    } <= issue_types
    assert any(item.severity == "blocker" for item in items)
    assert len(items) == len(repeated)
    assert all(item.evidence_snapshot.get("raw_line") != "hello Page PB p.1" or "origin" in item.evidence_snapshot for item in items)
