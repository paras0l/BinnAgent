from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.documents.artifact import DocumentBlock, DocumentParseArtifact


UNIT_HEADING_PATTERN = re.compile(r"^(?P<title>(?:Starter\s+)?Unit\s+\d+)\b(?P<rest>.*)$", re.I)
VOCABULARY_SECTION_PATTERN = re.compile(r"Words and Expressions(?: in Each Unit)?", re.I)
VOCABULARY_INDEX_PATTERN = re.compile(r"Vocabulary Index", re.I)
VOCABULARY_UNIT_PATTERN = re.compile(r"^(Starter\s+Unit|Unit)\s+(\d+)$", re.I)
VOCABULARY_PAGE_REF_PATTERN = re.compile(r"\s+p\.(S?\d+(?:[–-]S?\d+)?)\s*$", re.I)
PHONETIC_PATTERN = re.compile(r"^(?P<expression>.+?)\s+/[^/]+/(?:\s+[a-z]+\.)?.*$", re.I)
PART_OF_SPEECH_PATTERN = re.compile(
    r"\b(?:adj|adv|art|conj|interj|modal\s+v|n|num|prep|pron|v)\.",
    re.I,
)


@dataclass(frozen=True)
class ExtractionEvidence:
    page_number: int | None
    block_id: str | None
    parser_engine: str
    confidence: float

    def to_dict(self) -> dict[str, str | int | float | None]:
        return {
            "page_number": self.page_number,
            "block_id": self.block_id,
            "parser_engine": self.parser_engine,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class CurriculumCandidate:
    title: str
    subtitle: str
    page_number: int
    evidence: ExtractionEvidence


@dataclass(frozen=True)
class KnowledgeCandidate:
    canonical_key: str
    type: str
    title: str
    summary: str
    page_number: int
    confidence: float
    evidence: ExtractionEvidence
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class VocabularyCandidate:
    unit_title: str
    expression: str
    canonical_expression: str
    unit_order: int
    raw_line: str
    confidence: float
    evidence: ExtractionEvidence
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextbookExtractionResult:
    curriculum: tuple[CurriculumCandidate, ...] = ()
    knowledge: tuple[KnowledgeCandidate, ...] = ()
    vocabulary: tuple[VocabularyCandidate, ...] = ()
    exercises: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)


class TextbookExtractor:
    def extract(self, artifact: DocumentParseArtifact) -> TextbookExtractionResult:
        blocks = artifact.blocks or _blocks_from_pages(artifact)
        curriculum = _extract_curriculum(blocks, artifact)
        if not curriculum and (artifact.markdown.strip() or blocks):
            curriculum = (
                CurriculumCandidate(
                    title="全册材料",
                    subtitle="",
                    page_number=1,
                    evidence=ExtractionEvidence(
                        page_number=1,
                        block_id=blocks[0].id if blocks else None,
                        parser_engine=artifact.parser_engine,
                        confidence=0.45,
                    ),
                ),
            )
        knowledge = _extract_knowledge(curriculum, blocks, artifact.parser_engine)
        vocabulary = _extract_vocabulary(blocks, artifact.parser_engine)
        warnings = []
        if not curriculum:
            warnings.append("No curriculum units detected from document artifact.")
        if not vocabulary:
            warnings.append("No vocabulary candidates detected from document artifact.")
        return TextbookExtractionResult(
            curriculum=curriculum,
            knowledge=knowledge,
            vocabulary=vocabulary,
            warnings=tuple(warnings),
            metadata={
                "parser_engine": artifact.parser_engine,
                "block_count": len(blocks),
                "quality": artifact.quality_dict(),
            },
        )


def extract_textbook_candidates(artifact: DocumentParseArtifact) -> TextbookExtractionResult:
    return TextbookExtractor().extract(artifact)


def _blocks_from_pages(artifact: DocumentParseArtifact) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for page in artifact.pages:
        for order, paragraph in enumerate(_paragraphs(page.text), start=len(blocks)):
            blocks.append(
                DocumentBlock(
                    id=f"p{page.page_number}-b{order + 1}",
                    page_number=page.page_number,
                    type="paragraph",
                    text=paragraph,
                    reading_order=order,
                    confidence=0.7,
                    source=artifact.parser_engine,
                )
            )
    return blocks


def _extract_curriculum(
    blocks: list[DocumentBlock],
    artifact: DocumentParseArtifact,
) -> tuple[CurriculumCandidate, ...]:
    candidates: list[CurriculumCandidate] = []
    seen: set[str] = set()
    for index, block in enumerate(blocks):
        lines = [line.strip() for line in block.text.splitlines() if line.strip()]
        for line_index, line in enumerate(lines):
            match = UNIT_HEADING_PATTERN.match(line)
            if not match:
                continue
            title = _normalize_unit_title(match.group("title"))
            if title.casefold() in seen:
                continue
            subtitle = _compact_label(match.group("rest"), max_length=120)
            if not subtitle:
                subtitle = _next_subtitle(lines, line_index) or _next_block_subtitle(blocks, index)
            seen.add(title.casefold())
            candidates.append(
                CurriculumCandidate(
                    title=title,
                    subtitle=subtitle,
                    page_number=block.page_number or 1,
                    evidence=ExtractionEvidence(
                        page_number=block.page_number,
                        block_id=block.id,
                        parser_engine=artifact.parser_engine,
                        confidence=block.confidence,
                    ),
                )
            )
    candidates.sort(key=lambda item: (0 if item.title.startswith("Starter") else 1, item.page_number))
    return tuple(candidates[:30])


def _extract_knowledge(
    curriculum: tuple[CurriculumCandidate, ...],
    blocks: list[DocumentBlock],
    parser_engine: str,
) -> tuple[KnowledgeCandidate, ...]:
    knowledge: list[KnowledgeCandidate] = []
    for index, unit in enumerate(curriculum, start=1):
        slug = _slug(unit.title)
        title = f"{unit.title} overview"
        summary = unit.subtitle or f"通用教材单元：{unit.title}"
        knowledge.append(
            KnowledgeCandidate(
                canonical_key=f"unit-overview.{slug}.{index}",
                type="unit_overview",
                title=title,
                summary=summary,
                page_number=unit.page_number,
                confidence=min(0.8, unit.evidence.confidence),
                evidence=unit.evidence,
                warnings=("generic_candidate",),
            )
        )
    for block in blocks:
        if block.type != "heading" or UNIT_HEADING_PATTERN.match(block.text.strip()):
            continue
        text = " ".join(block.text.split())
        if len(text) < 4 or len(text) > 120:
            continue
        knowledge.append(
            KnowledgeCandidate(
                canonical_key=f"heading.{_slug(text)}.{block.reading_order}",
                type="topic",
                title=text,
                summary=f"从文档标题提取的知识候选：{text}",
                page_number=block.page_number or 1,
                confidence=min(0.72, block.confidence),
                evidence=ExtractionEvidence(
                    page_number=block.page_number,
                    block_id=block.id,
                    parser_engine=parser_engine,
                    confidence=block.confidence,
                ),
                warnings=("heading_only",),
            )
        )
    return tuple(knowledge)


def _extract_vocabulary(
    blocks: list[DocumentBlock],
    parser_engine: str,
) -> tuple[VocabularyCandidate, ...]:
    entries: list[VocabularyCandidate] = []
    in_section = False
    current_unit: str | None = None
    unit_orders: dict[str, int] = {}
    buffer: list[str] = []
    evidence_block: DocumentBlock | None = None
    for block in blocks:
        lines = [line.strip() for line in block.text.splitlines() if line.strip()]
        for line in lines:
            if VOCABULARY_INDEX_PATTERN.search(line):
                return tuple(entries)
            if VOCABULARY_SECTION_PATTERN.search(line):
                in_section = True
                continue
            if not in_section:
                continue
            unit_match = VOCABULARY_UNIT_PATTERN.fullmatch(line)
            if unit_match:
                current_unit = _normalize_unit_title(line)
                unit_orders.setdefault(current_unit, 0)
                buffer.clear()
                evidence_block = block
                continue
            if current_unit is None:
                continue
            buffer.append(line)
            evidence_block = evidence_block or block
            combined = " ".join(buffer)
            page_ref_match = VOCABULARY_PAGE_REF_PATTERN.search(combined)
            if not page_ref_match:
                continue
            raw = combined[: page_ref_match.start()].strip()
            unit_orders[current_unit] += 1
            entry = _parse_vocabulary_line(
                current_unit=current_unit,
                raw_line=raw,
                unit_order=unit_orders[current_unit],
                block=evidence_block or block,
                parser_engine=parser_engine,
            )
            if entry is not None:
                entries.append(entry)
            buffer.clear()
            evidence_block = None
    return tuple(entries)


def _parse_vocabulary_line(
    *,
    current_unit: str,
    raw_line: str,
    unit_order: int,
    block: DocumentBlock,
    parser_engine: str,
) -> VocabularyCandidate | None:
    normalized = " ".join(raw_line.split())
    phonetic_match = PHONETIC_PATTERN.match(normalized)
    if phonetic_match:
        expression = phonetic_match.group("expression")
    else:
        pos_match = PART_OF_SPEECH_PATTERN.search(normalized)
        cjk_match = re.search(r"[\u3400-\u9fff]", normalized)
        split_at = pos_match.start() if pos_match else cjk_match.start() if cjk_match else len(normalized)
        expression = normalized[:split_at]
    expression = _normalize_expression(expression)
    canonical = _canonical_expression(expression)
    if not canonical or not re.search(r"[a-z]", canonical) or len(expression) > 100:
        return None
    warnings: list[str] = []
    confidence = 0.86
    if not phonetic_match:
        confidence -= 0.1
        warnings.append("missing_phonetic")
    return VocabularyCandidate(
        unit_title=current_unit,
        expression=expression,
        canonical_expression=canonical,
        unit_order=unit_order,
        raw_line=normalized,
        confidence=max(0.0, confidence),
        warnings=tuple(warnings),
        evidence=ExtractionEvidence(
            page_number=block.page_number,
            block_id=block.id,
            parser_engine=parser_engine,
            confidence=max(0.0, confidence),
        ),
    )


def _paragraphs(text: str) -> list[str]:
    return [" ".join(part.split()) for part in text.split("\n\n") if " ".join(part.split())]


def _next_subtitle(lines: list[str], line_index: int) -> str:
    if line_index + 1 >= len(lines):
        return ""
    value = _compact_label(lines[line_index + 1], max_length=100)
    return value if 3 <= len(value) <= 100 and not UNIT_HEADING_PATTERN.match(value) else ""


def _next_block_subtitle(blocks: list[DocumentBlock], block_index: int) -> str:
    if block_index + 1 >= len(blocks):
        return ""
    value = _compact_label(blocks[block_index + 1].text, max_length=100)
    return value if 3 <= len(value) <= 100 and not UNIT_HEADING_PATTERN.match(value) else ""


def _compact_label(value: str, *, max_length: int) -> str:
    normalized = " ".join(value.split()).strip(" :·—-")
    if len(normalized) <= max_length:
        return normalized
    for separator in (". ", "。", "; ", "；", " / "):
        head = normalized.split(separator, 1)[0].strip(" :·—-")
        if 3 <= len(head) <= max_length:
            return head
    return normalized[: max_length - 1].rstrip(" :·—-") + "…"


def _normalize_unit_title(value: str) -> str:
    match = VOCABULARY_UNIT_PATTERN.match(" ".join(value.split()))
    if not match:
        return " ".join(value.split())
    prefix = "Starter Unit" if match.group(1).lower().startswith("starter") else "Unit"
    return f"{prefix} {int(match.group(2))}"


def _normalize_expression(value: str) -> str:
    expression = " ".join(value.split()).strip(" ·—-")
    expression = re.sub(r"\bY\s+ou", "You", expression)
    return expression.replace("_", "").strip(" （").strip()


def _canonical_expression(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "candidate"
