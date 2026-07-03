from dataclasses import dataclass, field
from typing import Any

from src.knowledge.parser_profiles import ParserProfile


@dataclass(frozen=True)
class ParserQualityReport:
    parser_profile: str | None
    unit_count: int
    expected_unit_count: int | None
    vocabulary_entry_count: int
    expected_min_vocabulary_count: int | None
    low_confidence_entries: int
    dirty_tokens: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    page_count: int | None = None
    text_char_count: int | None = None
    avg_text_chars_per_page: float | None = None
    empty_page_ratio: float | None = None
    has_text_layer: bool | None = None
    is_scanned_pdf_suspected: bool | None = None
    unit_title_match_rate: float | None = None
    unit_order_valid: bool | None = None
    section_count: int | None = None
    section_coverage_rate: float | None = None
    knowledge_count_by_type: dict[str, int] = field(default_factory=dict)
    source_page_coverage_rate: float | None = None
    evidence_ref_coverage_rate: float | None = None
    duplicate_knowledge_count: int | None = None
    requires_review_count: int | None = None
    core_vocabulary_hit_rate: float | None = None
    low_confidence_vocabulary_ratio: float | None = None
    dirty_token_entry_count: int | None = None
    rag_chunk_count: int | None = None
    rag_page_coverage_rate: float | None = None
    chunk_avg_size: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser_profile": self.parser_profile,
            "unit_count": self.unit_count,
            "expected_unit_count": self.expected_unit_count,
            "vocabulary_entry_count": self.vocabulary_entry_count,
            "expected_min_vocabulary_count": self.expected_min_vocabulary_count,
            "low_confidence_entries": self.low_confidence_entries,
            "dirty_tokens": self.dirty_tokens,
            "warnings": self.warnings,
            "page_count": self.page_count,
            "text_char_count": self.text_char_count,
            "avg_text_chars_per_page": self.avg_text_chars_per_page,
            "empty_page_ratio": self.empty_page_ratio,
            "has_text_layer": self.has_text_layer,
            "is_scanned_pdf_suspected": self.is_scanned_pdf_suspected,
            "unit_title_match_rate": self.unit_title_match_rate,
            "unit_order_valid": self.unit_order_valid,
            "section_count": self.section_count,
            "section_coverage_rate": self.section_coverage_rate,
            "knowledge_count_by_type": self.knowledge_count_by_type,
            "source_page_coverage_rate": self.source_page_coverage_rate,
            "evidence_ref_coverage_rate": self.evidence_ref_coverage_rate,
            "duplicate_knowledge_count": self.duplicate_knowledge_count,
            "requires_review_count": self.requires_review_count,
            "core_vocabulary_hit_rate": self.core_vocabulary_hit_rate,
            "low_confidence_vocabulary_ratio": self.low_confidence_vocabulary_ratio,
            "dirty_token_entry_count": self.dirty_token_entry_count,
            "rag_chunk_count": self.rag_chunk_count,
            "rag_page_coverage_rate": self.rag_page_coverage_rate,
            "chunk_avg_size": self.chunk_avg_size,
        }


def build_parser_report(
    *,
    profile: ParserProfile | None,
    unit_count: int,
    vocabulary_entries: list[Any] | tuple[Any, ...],
    page_texts: list[str],
    unit_titles: list[str] | tuple[str, ...] | None = None,
    knowledge_points: list[Any] | tuple[Any, ...] | None = None,
    section_count: int | None = None,
    rag_chunk_count: int | None = None,
    rag_covered_pages: set[int] | None = None,
    chunk_char_counts: list[int] | tuple[int, ...] | None = None,
) -> ParserQualityReport:
    warnings: list[str] = []
    expected_unit_count = profile.expected_unit_count if profile else None
    min_vocabulary_count = profile.min_vocabulary_count if profile else None
    if expected_unit_count is not None and unit_count != expected_unit_count:
        warnings.append(f"Unit count {unit_count} differs from expected {expected_unit_count}.")
    if min_vocabulary_count is not None and len(vocabulary_entries) < min_vocabulary_count:
        warnings.append(
            f"Vocabulary count {len(vocabulary_entries)} is lower than expected minimum {min_vocabulary_count}."
        )
    low_confidence = sum(
        1 for entry in vocabulary_entries if float(getattr(entry, "confidence", 1.0)) < 0.75
    )
    if low_confidence:
        warnings.append(f"{low_confidence} vocabulary entries require review.")
    dirty_tokens = _found_dirty_tokens(profile, page_texts)
    if dirty_tokens:
        warnings.append("Dirty PDF tokens were detected in extracted text.")
    page_count = len(page_texts)
    text_char_count = sum(len(text or "") for text in page_texts)
    non_empty_pages = sum(1 for text in page_texts if (text or "").strip())
    empty_page_ratio = _ratio(page_count - non_empty_pages, page_count)
    avg_text_chars_per_page = (
        round(text_char_count / page_count, 2) if page_count else None
    )
    has_text_layer = bool(text_char_count)
    is_scanned_pdf_suspected = bool(page_count and text_char_count < max(200, page_count * 20))
    unit_title_match_rate = _unit_title_match_rate(profile, unit_titles or ())
    unit_order_valid = _unit_order_valid(unit_titles or ())
    knowledge_metrics = _knowledge_metrics(knowledge_points or ())
    core_vocabulary_hit_rate = _core_vocabulary_hit_rate(profile, vocabulary_entries)
    low_confidence_ratio = _ratio(low_confidence, len(vocabulary_entries))
    dirty_token_entry_count = _dirty_token_entry_count(vocabulary_entries, dirty_tokens)
    rag_page_coverage_rate = _ratio(len(rag_covered_pages or set()), non_empty_pages)
    chunk_avg_size = (
        round(sum(chunk_char_counts) / len(chunk_char_counts), 2)
        if chunk_char_counts
        else None
    )
    section_coverage_rate = _ratio(section_count, unit_count) if section_count is not None else None
    return ParserQualityReport(
        parser_profile=profile.id if profile else None,
        unit_count=unit_count,
        expected_unit_count=expected_unit_count,
        vocabulary_entry_count=len(vocabulary_entries),
        expected_min_vocabulary_count=min_vocabulary_count,
        low_confidence_entries=low_confidence,
        dirty_tokens=dirty_tokens,
        warnings=warnings,
        page_count=page_count,
        text_char_count=text_char_count,
        avg_text_chars_per_page=avg_text_chars_per_page,
        empty_page_ratio=empty_page_ratio,
        has_text_layer=has_text_layer,
        is_scanned_pdf_suspected=is_scanned_pdf_suspected,
        unit_title_match_rate=unit_title_match_rate,
        unit_order_valid=unit_order_valid,
        section_count=section_count,
        section_coverage_rate=section_coverage_rate,
        knowledge_count_by_type=knowledge_metrics["knowledge_count_by_type"],
        source_page_coverage_rate=knowledge_metrics["source_page_coverage_rate"],
        evidence_ref_coverage_rate=knowledge_metrics["evidence_ref_coverage_rate"],
        duplicate_knowledge_count=knowledge_metrics["duplicate_knowledge_count"],
        requires_review_count=knowledge_metrics["requires_review_count"],
        core_vocabulary_hit_rate=core_vocabulary_hit_rate,
        low_confidence_vocabulary_ratio=low_confidence_ratio,
        dirty_token_entry_count=dirty_token_entry_count,
        rag_chunk_count=rag_chunk_count,
        rag_page_coverage_rate=rag_page_coverage_rate,
        chunk_avg_size=chunk_avg_size,
    )


def _found_dirty_tokens(profile: ParserProfile | None, page_texts: list[str]) -> list[str]:
    tokens = profile.dirty_tokens if profile else ("Page PB", "9594", "101100")
    joined = "\n".join(page_texts)
    return [token for token in tokens if token in joined]


def _ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if denominator in (None, 0) or numerator is None:
        return None
    return round(max(0.0, min(1.0, float(numerator) / float(denominator))), 4)


def _unit_title_match_rate(
    profile: ParserProfile | None,
    unit_titles: list[str] | tuple[str, ...],
) -> float | None:
    expected = profile.expected_unit_titles if profile else ()
    if not expected:
        return None
    normalized = {_normalize(title) for title in unit_titles}
    matched = sum(1 for title in expected if _normalize(title) in normalized)
    return _ratio(matched, len(expected))


def _unit_order_valid(unit_titles: list[str] | tuple[str, ...]) -> bool | None:
    unit_numbers: list[int] = []
    for title in unit_titles:
        parts = str(title).split()
        if parts and parts[-1].isdigit():
            unit_numbers.append(int(parts[-1]))
    if len(unit_numbers) < 2:
        return None
    return unit_numbers == sorted(unit_numbers)


def _knowledge_metrics(knowledge_points: list[Any] | tuple[Any, ...]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    source_page_count = 0
    evidence_count = 0
    requires_review_count = 0
    canonical_keys: set[str] = set()
    duplicate_count = 0
    for point in knowledge_points:
        point_type = str(getattr(point, "type", "unknown") or "unknown")
        by_type[point_type] = by_type.get(point_type, 0) + 1
        source_page = str(getattr(point, "source_page", "") or "").strip()
        if source_page:
            source_page_count += 1
        content = getattr(point, "content", None) or {}
        if (
            content.get("evidence_refs")
            or content.get("evidence_pdf_pages")
            or content.get("raw_line")
            or source_page
        ):
            evidence_count += 1
        if content.get("requires_review"):
            requires_review_count += 1
        canonical_key = str(getattr(point, "canonical_key", "") or "")
        if canonical_key in canonical_keys:
            duplicate_count += 1
        canonical_keys.add(canonical_key)
    total = len(knowledge_points)
    return {
        "knowledge_count_by_type": by_type,
        "source_page_coverage_rate": _ratio(source_page_count, total),
        "evidence_ref_coverage_rate": _ratio(evidence_count, total),
        "duplicate_knowledge_count": duplicate_count,
        "requires_review_count": requires_review_count,
    }


def _core_vocabulary_hit_rate(
    profile: ParserProfile | None,
    vocabulary_entries: list[Any] | tuple[Any, ...],
) -> float | None:
    expected = profile.expected_core_vocabulary if profile else ()
    if not expected:
        return None
    parsed = {
        _normalize(getattr(entry, "canonical_expression", getattr(entry, "expression", "")))
        for entry in vocabulary_entries
    }
    hits = sum(1 for item in expected if _normalize(item) in parsed)
    return _ratio(hits, len(expected))


def _dirty_token_entry_count(
    vocabulary_entries: list[Any] | tuple[Any, ...],
    dirty_tokens: list[str],
) -> int:
    if not dirty_tokens:
        return 0
    return sum(
        1
        for entry in vocabulary_entries
        if any(token in str(getattr(entry, "raw_line", "")) for token in dirty_tokens)
    )


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())
