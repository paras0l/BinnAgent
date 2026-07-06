from types import SimpleNamespace

from src.knowledge.parser_profiles import ParserProfile
from src.knowledge.parser_report import build_parser_report


def test_parser_quality_report_emits_intake_structure_knowledge_and_rag_metrics() -> None:
    profile = ParserProfile(
        id="test-profile",
        expected_unit_count=2,
        min_vocabulary_count=2,
        expected_unit_titles=("Unit 1", "Unit 2"),
        expected_core_vocabulary=("hello", "school"),
    )
    entries = [
        SimpleNamespace(
            expression="hello",
            canonical_expression="hello",
            raw_line="hello p.1",
            confidence=0.95,
        ),
        SimpleNamespace(
            expression="school",
            canonical_expression="school",
            raw_line="school p.2",
            confidence=0.6,
        ),
    ]
    points = [
        SimpleNamespace(
            type="vocabulary",
            source_page="P.1",
            canonical_key="vocabulary.hello",
            content={"raw_line": "hello p.1", "requires_review": False},
        ),
        SimpleNamespace(
            type="grammar",
            source_page="",
            canonical_key="grammar.be",
            content={"requires_review": True},
        ),
        SimpleNamespace(
            type="grammar",
            source_page="P.2",
            canonical_key="grammar.be",
            content={"evidence_refs": ["P.2"], "requires_review": False},
        ),
    ]

    report = build_parser_report(
        profile=profile,
        unit_count=2,
        vocabulary_entries=entries,
        page_texts=["hello " * 20, "", "school " * 10],
        unit_titles=("Unit 1", "Unit 2"),
        knowledge_points=points,
        section_count=2,
        rag_chunk_count=3,
        rag_covered_pages={1, 3},
        chunk_char_counts=[220, 240, 260],
    )
    payload = report.to_dict()

    assert payload["page_count"] == 3
    assert payload["empty_page_ratio"] == 0.3333
    assert payload["unit_title_match_rate"] == 1.0
    assert payload["knowledge_count_by_type"] == {"vocabulary": 1, "grammar": 2}
    assert payload["source_page_coverage_rate"] == 0.6667
    assert payload["evidence_ref_coverage_rate"] == 0.6667
    assert payload["duplicate_knowledge_count"] == 1
    assert payload["requires_review_count"] == 1
    assert payload["core_vocabulary_hit_rate"] == 1.0
    assert payload["low_confidence_vocabulary_ratio"] == 0.5
    assert payload["rag_page_coverage_rate"] == 1.0
    assert payload["chunk_avg_size"] == 240.0


def test_parser_quality_report_accepts_starter_units_before_regular_units() -> None:
    profile = ParserProfile(
        id="starter-profile",
        expected_unit_count=5,
        expected_unit_titles=("Starter Unit 1", "Starter Unit 2", "Starter Unit 3", "Unit 1", "Unit 2"),
    )

    report = build_parser_report(
        profile=profile,
        unit_count=5,
        vocabulary_entries=[],
        page_texts=["Starter Unit 1"],
        unit_titles=("Starter Unit 1", "Starter Unit 2", "Starter Unit 3", "Unit 1", "Unit 2"),
    )

    assert report.unit_order_valid is True
