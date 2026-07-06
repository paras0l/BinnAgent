from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MIN_CORE_VOCABULARY_HIT_RATE = 0.9
MAX_LOW_CONFIDENCE_VOCABULARY_RATIO = 0.1
MIN_SOURCE_PAGE_COVERAGE_RATE = 0.95
MIN_EVIDENCE_REF_COVERAGE_RATE = 0.9
MAX_DIRTY_TOKEN_ENTRY_COUNT = 0
MIN_RAG_PAGE_COVERAGE_RATE = 0.95
MAX_REQUIRES_REVIEW_COUNT = 0
MIN_STRUCTURE_SCORE = 0.7


@dataclass(frozen=True)
class TextbookQualityScore:
    overall_score: float
    structure_score: float
    vocabulary_score: float
    rag_score: float
    provenance_score: float
    status: str
    blocking_reasons: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_textbook_quality(
    report: dict[str, Any],
    *,
    parser_failed: bool = False,
) -> TextbookQualityScore:
    blocking_reasons: list[str] = []
    warnings: list[str] = list(report.get("warnings") or [])

    if parser_failed:
        blocking_reasons.append("Parser run failed.")
    if report.get("is_scanned_pdf_suspected"):
        blocking_reasons.append("PDF appears to be scanned and has no usable text layer.")
    if int(report.get("unit_count") or 0) == 0:
        blocking_reasons.append("No textbook units were parsed.")

    expected_unit_count = report.get("expected_unit_count")
    unit_count = int(report.get("unit_count") or 0)
    if isinstance(expected_unit_count, int) and expected_unit_count > 0:
        unit_ratio = unit_count / expected_unit_count
        if unit_ratio < 0.5:
            blocking_reasons.append("Parsed unit count is far below the expected textbook structure.")
        elif unit_ratio < 0.9:
            warnings.append("Parsed unit count is below the expected textbook structure.")

    source_page_coverage = _ratio(report.get("source_page_coverage_rate"))
    if source_page_coverage is not None and source_page_coverage < 0.5:
        blocking_reasons.append("Source page coverage is too low for safe learning use.")
    elif source_page_coverage is not None and source_page_coverage < MIN_SOURCE_PAGE_COVERAGE_RATE:
        warnings.append("Source page coverage is below the publishing threshold.")

    dirty_count = int(report.get("dirty_token_entry_count") or 0)
    if dirty_count > 20:
        blocking_reasons.append("Dirty PDF tokens are widespread in parsed entries.")
    elif dirty_count > MAX_DIRTY_TOKEN_ENTRY_COUNT:
        warnings.append("Dirty PDF tokens were detected.")

    core_hit_rate = _ratio(report.get("core_vocabulary_hit_rate"))
    vocabulary_count_ratio = _vocabulary_count_ratio(report)
    has_enough_vocabulary = vocabulary_count_ratio is not None and vocabulary_count_ratio >= 1.0
    if core_hit_rate is not None and core_hit_rate < 0.25 and not has_enough_vocabulary:
        blocking_reasons.append("Core vocabulary hit rate is extremely low.")
    elif core_hit_rate is not None and core_hit_rate < MIN_CORE_VOCABULARY_HIT_RATE:
        warnings.append("Core vocabulary hit rate is below the publishing threshold.")

    low_conf_ratio = _ratio(report.get("low_confidence_vocabulary_ratio"))
    if (
        low_conf_ratio is not None
        and low_conf_ratio > MAX_LOW_CONFIDENCE_VOCABULARY_RATIO
    ):
        warnings.append("Low confidence vocabulary ratio is above the publishing threshold.")

    evidence_coverage = _ratio(report.get("evidence_ref_coverage_rate"))
    if evidence_coverage is not None and evidence_coverage < MIN_EVIDENCE_REF_COVERAGE_RATE:
        warnings.append("Evidence reference coverage is below the publishing threshold.")

    rag_coverage = _ratio(report.get("rag_page_coverage_rate"))
    rag_chunk_count = int(report.get("rag_chunk_count") or 0)
    if rag_chunk_count == 0:
        warnings.append("No RAG chunks were produced.")
    elif rag_coverage is not None and rag_coverage < MIN_RAG_PAGE_COVERAGE_RATE:
        warnings.append("RAG page coverage is below the publishing threshold.")

    requires_review_count = int(report.get("requires_review_count") or 0)
    if requires_review_count > MAX_REQUIRES_REVIEW_COUNT:
        warnings.append("Parser review items are still pending.")
    pending_blocker_count = int(report.get("pending_blocker_count") or 0)
    if pending_blocker_count > 0:
        blocking_reasons.append("Parser review blockers are still pending.")

    structure_score = _bounded_average(
        _ratio(report.get("unit_title_match_rate")),
        1.0 if report.get("unit_order_valid", True) else 0.0,
        _ratio(report.get("section_coverage_rate")),
    )
    vocabulary_score = _bounded_average(
        max(core_hit_rate or 0.0, vocabulary_count_ratio or 0.0)
        if core_hit_rate is not None or vocabulary_count_ratio is not None
        else None,
        _inverse_ratio(low_conf_ratio),
        1.0 if dirty_count == 0 else max(0.0, 1.0 - dirty_count / 20),
    )
    rag_score = _bounded_average(
        1.0 if rag_chunk_count > 0 else 0.0,
        rag_coverage,
        _chunk_size_score(report.get("chunk_avg_size")),
    )
    provenance_score = _bounded_average(
        source_page_coverage,
        evidence_coverage,
        1.0 if requires_review_count == 0 else max(0.0, 1.0 - requires_review_count / 20),
    )
    overall = round(
        (structure_score * 0.3)
        + (vocabulary_score * 0.25)
        + (rag_score * 0.2)
        + (provenance_score * 0.25),
        4,
    )

    status = _status(
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        report=report,
        structure_score=structure_score,
        rag_chunk_count=rag_chunk_count,
        requires_review_count=requires_review_count,
    )
    return TextbookQualityScore(
        overall_score=overall,
        structure_score=round(structure_score, 4),
        vocabulary_score=round(vocabulary_score, 4),
        rag_score=round(rag_score, 4),
        provenance_score=round(provenance_score, 4),
        status=status,
        blocking_reasons=blocking_reasons,
        warnings=_dedupe(warnings),
    )


def quality_summary(score: TextbookQualityScore, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "quality_status": score.status,
        "availability_status": availability_status_for_quality(score.status),
        "quality_score": score.to_dict(),
        "blocking_reasons": score.blocking_reasons,
        "pending_review_count": int(report.get("requires_review_count") or 0),
        "pending_blocker_count": int(report.get("pending_blocker_count") or 0),
        "review_warning_count": int(report.get("review_warning_count") or 0),
        "parser_report_summary": {
            "page_count": report.get("page_count"),
            "text_char_count": report.get("text_char_count"),
            "has_text_layer": report.get("has_text_layer"),
            "is_scanned_pdf_suspected": report.get("is_scanned_pdf_suspected"),
            "unit_count": report.get("unit_count"),
            "expected_unit_count": report.get("expected_unit_count"),
            "vocabulary_entry_count": report.get("vocabulary_entry_count"),
            "expected_min_vocabulary_count": report.get("expected_min_vocabulary_count"),
            "vocabulary_count_coverage_rate": _vocabulary_count_ratio(report),
            "rag_chunk_count": report.get("rag_chunk_count"),
            "requires_review_count": report.get("requires_review_count"),
            "pending_blocker_count": report.get("pending_blocker_count"),
            "review_warning_count": report.get("review_warning_count"),
            "source_page_coverage_rate": report.get("source_page_coverage_rate"),
            "core_vocabulary_hit_rate": report.get("core_vocabulary_hit_rate"),
            "warnings": report.get("warnings") or [],
        },
    }


def _status(
    *,
    blocking_reasons: list[str],
    warnings: list[str],
    report: dict[str, Any],
    structure_score: float,
    rag_chunk_count: int,
    requires_review_count: int,
) -> str:
    if any(reason == "Parser run failed." for reason in blocking_reasons):
        return "failed"
    if any("scanned" in reason for reason in blocking_reasons):
        return "failed"
    if blocking_reasons:
        if rag_chunk_count > 0 and structure_score < MIN_STRUCTURE_SCORE:
            return "partial_indexed"
        return "blocked"
    if requires_review_count > 0:
        return "review_required"
    if warnings:
        if rag_chunk_count > 0 and structure_score < MIN_STRUCTURE_SCORE:
            return "partial_indexed"
        return "review_required"
    if _meets_publishing_thresholds(report):
        return "published"
    return "review_required"


def availability_status_for_quality(quality_status: str) -> str:
    if quality_status == "published":
        return "available"
    if quality_status == "partial_indexed":
        return "partially_available"
    if quality_status == "review_required":
        return "needs_review"
    return "unavailable"


def _meets_publishing_thresholds(report: dict[str, Any]) -> bool:
    checks = [
        (
            _ratio(report.get("core_vocabulary_hit_rate"), default=1.0)
            >= MIN_CORE_VOCABULARY_HIT_RATE
            or _vocabulary_count_ratio(report, default=0.0) >= 1.0
        ),
        _ratio(report.get("low_confidence_vocabulary_ratio"), default=0.0)
        <= MAX_LOW_CONFIDENCE_VOCABULARY_RATIO,
        _ratio(report.get("source_page_coverage_rate"), default=1.0)
        >= MIN_SOURCE_PAGE_COVERAGE_RATE,
        _ratio(report.get("evidence_ref_coverage_rate"), default=1.0)
        >= MIN_EVIDENCE_REF_COVERAGE_RATE,
        int(report.get("dirty_token_entry_count") or 0) == MAX_DIRTY_TOKEN_ENTRY_COUNT,
        _ratio(report.get("rag_page_coverage_rate"), default=1.0)
        >= MIN_RAG_PAGE_COVERAGE_RATE,
        int(report.get("requires_review_count") or 0) == MAX_REQUIRES_REVIEW_COUNT,
        int(report.get("pending_blocker_count") or 0) == 0,
    ]
    return all(checks)


def _ratio(value: Any, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _vocabulary_count_ratio(report: dict[str, Any], *, default: float | None = None) -> float | None:
    expected = report.get("expected_min_vocabulary_count")
    if not isinstance(expected, int) or expected <= 0:
        return default
    try:
        actual = int(report.get("vocabulary_entry_count") or 0)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, actual / expected))


def _inverse_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, 1.0 - value))


def _bounded_average(*values: float | None) -> float:
    valid = [value for value in values if value is not None]
    if not valid:
        return 1.0
    return sum(max(0.0, min(1.0, value)) for value in valid) / len(valid)


def _chunk_size_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        size = float(value)
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return 0.0
    if 200 <= size <= 1200:
        return 1.0
    if size < 200:
        return size / 200
    return max(0.0, 1.0 - ((size - 1200) / 1200))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
