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
        }


def build_parser_report(
    *,
    profile: ParserProfile | None,
    unit_count: int,
    vocabulary_entries: list[Any] | tuple[Any, ...],
    page_texts: list[str],
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
    return ParserQualityReport(
        parser_profile=profile.id if profile else None,
        unit_count=unit_count,
        expected_unit_count=expected_unit_count,
        vocabulary_entry_count=len(vocabulary_entries),
        expected_min_vocabulary_count=min_vocabulary_count,
        low_confidence_entries=low_confidence,
        dirty_tokens=dirty_tokens,
        warnings=warnings,
    )


def _found_dirty_tokens(profile: ParserProfile | None, page_texts: list[str]) -> list[str]:
    tokens = profile.dirty_tokens if profile else ("Page PB", "9594", "101100")
    joined = "\n".join(page_texts)
    return [token for token in tokens if token in joined]
