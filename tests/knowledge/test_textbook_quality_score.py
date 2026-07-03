from src.knowledge.quality import score_textbook_quality


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
        "requires_review_count": 0,
        "rag_chunk_count": 48,
        "rag_page_coverage_rate": 1.0,
        "chunk_avg_size": 480,
        "warnings": [],
    }


def test_quality_score_publishes_when_all_thresholds_pass() -> None:
    score = score_textbook_quality(_healthy_report())

    assert score.status == "published"
    assert score.blocking_reasons == []
    assert score.overall_score == 1.0


def test_quality_score_requires_review_for_pending_parser_items() -> None:
    report = {**_healthy_report(), "requires_review_count": 2}

    score = score_textbook_quality(report)

    assert score.status == "review_required"
    assert "Parser review items are still pending." in score.warnings


def test_quality_score_blocks_when_provenance_is_too_low() -> None:
    report = {**_healthy_report(), "source_page_coverage_rate": 0.3}

    score = score_textbook_quality(report)

    assert score.status == "blocked"
    assert "Source page coverage is too low for safe learning use." in score.blocking_reasons


def test_quality_score_fails_scanned_or_failed_parser_runs() -> None:
    scanned = score_textbook_quality({**_healthy_report(), "is_scanned_pdf_suspected": True})
    failed = score_textbook_quality(_healthy_report(), parser_failed=True)

    assert scanned.status == "failed"
    assert failed.status == "failed"
