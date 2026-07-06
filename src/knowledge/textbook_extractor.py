from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from src.documents.artifact import DocumentBlock, DocumentParseArtifact


UNIT_HEADING_PATTERN = re.compile(r"^(?P<title>(?:Starter\s+)?Unit\s+\d+)\b(?P<rest>.*)$", re.I)
VOCABULARY_SECTION_PATTERN = re.compile(
    r"^Words and Expressions(?: in Each Unit)?(?:\s+\d{2,6})?$",
    re.I,
)
VOCABULARY_INDEX_PATTERN = re.compile(r"Vocabulary Index", re.I)
VOCABULARY_UNIT_PATTERN = re.compile(r"^(Starter\s+Unit|Unit)\s+(\d+)$", re.I)
VOCABULARY_PAGE_REF_PATTERN = re.compile(
    r"\s+[pP][.\-]?\s*(?:S?\d+|\d+[A-Za-z]?|[A-Za-z]{1,3}\d*|[1lI])\s*$",
    re.I,
)
VOCABULARY_ANY_PAGE_REF_PATTERN = re.compile(
    r"\s+[pP][.\-]?\s*(?:S?\d+|\d+[A-Za-z]?|[A-Za-z]{1,3}\d*|[1lI])\b.*$",
    re.I,
)
LAYOUT_UNIT_PATTERN = re.compile(
    r"^(?P<prefix>Starter\s+Unit|Unit)\s*(?P<number>\d+|[$S])?(?P<rest>.*)$",
    re.I,
)
NOISE_LINE_PATTERN = re.compile(r"^(?:Page\s+PB|\d{2,6})$", re.I)
PHONETIC_PATTERN = re.compile(r"^(?P<expression>.+?)\s*/[^/]+/(?:\s+[a-z]+\.)?.*$", re.I)
PART_OF_SPEECH_PATTERN = re.compile(
    r"\b(?:adj|adv|art|conj|interj|modal\s+v|n|num|prep|pron|v)\.",
    re.I,
)
GRAMMAR_HEADING_PATTERN = re.compile(r"^(?P<marker>[IVX]+|\d+)\s*\.\s*(?P<title>.+)$")
GRAMMAR_SECTION_PATTERN = re.compile(r"^Grammar\b", re.I)
PRONUNCIATION_SECTION_PATTERN = re.compile(r"^Pronunciation\b", re.I)
NOTES_SECTION_PATTERN = re.compile(r"Notes\s*on\s*the\s*Text|Noteson\s*the\s*Text", re.I)
TAPESCRIPTS_SECTION_PATTERN = re.compile(r"^Tapescripts\b", re.I)
APPENDIX_STOP_PATTERN = re.compile(r"^(?:Words and Expressions|Vocabulary Index|Name List|Irregular Verbs)$", re.I)
LANGUAGE_GOALS_PATTERN = re.compile(r"^Language Goals:\s*(?P<goals>.+)$", re.I)
ACTIVITY_CODE_PATTERN = re.compile(r"^(?P<code>\d+[a-z])(?:\s+(?P<title>.+))?$", re.I)
ACTIVITY_TRAILING_CODE_PATTERN = re.compile(r"^(?P<title>.+?)(?P<code>\d+[a-z])$", re.I)
INLINE_UNIT_PATTERN = re.compile(r"\bUnit\s*(?P<number>[1-9]|1[0-2]|S)\b(?P<rest>[^0-9]*)", re.I)
NOTE_ITEM_PATTERN = re.compile(r"(?P<number>\d{1,2})[.,]\s*(?P<text>.+)")
GRAMMAR_TOPIC_FRAGMENT_PATTERN = re.compile(
    r"(情态动词\s*[（(]\s*Modal\s*Verbs?\s*[）)]|"
    r"现在进行时\s*[（(]\s*Present\s*Progressive\s*Tense\s*[）)]|"
    r"一\s*般\s*过\s*去\s*时\s*[（(]\s*Simple\s*Past\s*Tense\s*[）)]|"
    r"There\s+be\s+结构|"
    r"介\s*[词间]\s*[（(]\s*Prepositions?\s*[）)]|"
    r"句\s*子\s*种\s*类\s*[（(]\s*Sentence\s*Types?\s*[）)]|"
    r"祈\s*使\s*[句名]|"
    r"选择\s*疑问\s*[句名])",
    re.I,
)
PRONUNCIATION_TOPIC_PATTERN = re.compile(
    r"(在\s*单词\s*中\s*的\s*读音|朗读\s*基本\s*知识|Sentence\s*Stress|Incomplete\s*Plosion|"
    r"Assimilation|Sense\s*Group|Rhythm|Intonation|语调|节奏|意群|不完全爆破|音的同化)",
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
class LayoutLine:
    page_number: int
    column: int
    y: float
    text: str
    block_id: str


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
        blocks = _blocks_for_extraction(artifact)
        page_blocks = _page_blocks_for_extraction(artifact)
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
        knowledge = _extract_knowledge(
            curriculum,
            blocks,
            artifact.parser_engine,
            marked_blocks=page_blocks or blocks,
        )
        vocabulary = _extract_vocabulary_from_layout(artifact)
        if not vocabulary and page_blocks:
            vocabulary = _extract_vocabulary(page_blocks, artifact.parser_engine)
        if not vocabulary:
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


def _page_blocks_for_extraction(artifact: DocumentParseArtifact) -> list[DocumentBlock]:
    return [
        DocumentBlock(
            id=f"page-{page.page_number}",
            page_number=page.page_number,
            type="page",
            text=page.text,
            reading_order=index,
            confidence=0.74,
            source=page.source or artifact.parser_engine,
        )
        for index, page in enumerate(artifact.pages)
        if page.text.strip()
    ]


def _blocks_for_extraction(artifact: DocumentParseArtifact) -> list[DocumentBlock]:
    page_blocks = _page_blocks_for_extraction(artifact)
    if page_blocks:
        if _blocks_look_line_collapsed(artifact.blocks, page_blocks):
            return [*page_blocks, *artifact.blocks]
        return [*artifact.blocks, *page_blocks]
    return artifact.blocks or _blocks_from_pages(artifact)


def _blocks_look_line_collapsed(
    blocks: list[DocumentBlock],
    page_blocks: list[DocumentBlock],
) -> bool:
    if not blocks:
        return True
    page_line_count = sum(block.text.count("\n") for block in page_blocks)
    block_line_count = sum(block.text.count("\n") for block in blocks)
    return page_line_count > block_line_count * 3


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
    candidates.sort(key=lambda item: _unit_sort_key(item.title, item.page_number))
    return tuple(candidates[:30])


def _extract_knowledge(
    curriculum: tuple[CurriculumCandidate, ...],
    blocks: list[DocumentBlock],
    parser_engine: str,
    *,
    marked_blocks: list[DocumentBlock] | None = None,
) -> tuple[KnowledgeCandidate, ...]:
    knowledge: list[KnowledgeCandidate] = []
    seen_keys: set[str] = set()
    marked_blocks = marked_blocks or blocks
    for index, unit in enumerate(curriculum, start=1):
        slug = _slug(unit.title)
        title = f"{unit.title} overview"
        summary = unit.subtitle or f"通用教材单元：{unit.title}"
        canonical_key = f"unit-overview.{slug}.{index}"
        seen_keys.add(canonical_key)
        knowledge.append(
            KnowledgeCandidate(
                canonical_key=canonical_key,
                type="unit_overview",
                title=title,
                summary=summary,
                page_number=unit.page_number,
                confidence=min(0.8, unit.evidence.confidence),
                evidence=unit.evidence,
                warnings=("generic_candidate",),
            )
        )
    for candidate in _extract_appendix_knowledge(marked_blocks, parser_engine):
        if candidate.canonical_key in seen_keys:
            continue
        seen_keys.add(candidate.canonical_key)
        knowledge.append(candidate)
    for candidate in _extract_notes_knowledge(marked_blocks, parser_engine):
        if candidate.canonical_key in seen_keys:
            continue
        seen_keys.add(candidate.canonical_key)
        knowledge.append(candidate)
    for candidate in _extract_unit_marked_knowledge(marked_blocks, parser_engine):
        if candidate.canonical_key in seen_keys:
            continue
        seen_keys.add(candidate.canonical_key)
        knowledge.append(candidate)
    for block in blocks:
        if block.type != "heading" or UNIT_HEADING_PATTERN.match(block.text.strip()):
            continue
        text = " ".join(block.text.split())
        if len(text) < 4 or len(text) > 120:
            continue
        canonical_key = f"heading.{_slug(text)}.{block.reading_order}"
        if canonical_key in seen_keys:
            continue
        seen_keys.add(canonical_key)
        knowledge.append(
            KnowledgeCandidate(
                canonical_key=canonical_key,
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


def _extract_unit_marked_knowledge(
    blocks: list[DocumentBlock],
    parser_engine: str,
) -> tuple[KnowledgeCandidate, ...]:
    candidates: list[KnowledgeCandidate] = []
    seen: set[str] = set()
    current_unit: str | None = None
    pending_activity_code: str | None = None
    sentence_counts: dict[str, int] = {}
    in_tapescripts = False
    for block in blocks:
        lines = [_clean_pdf_text(line) for line in block.text.splitlines()]
        lines = [line for line in lines if line and not _is_noise_line(line)]
        for line in lines:
            if TAPESCRIPTS_SECTION_PATTERN.match(line):
                current_unit = None
                pending_activity_code = None
                in_tapescripts = True
                continue
            if in_tapescripts:
                continue
            unit_match = UNIT_HEADING_PATTERN.match(line)
            if unit_match:
                current_unit = _normalize_unit_title(unit_match.group("title"))
                pending_activity_code = None
                continue
            if current_unit is None:
                continue

            evidence = ExtractionEvidence(
                page_number=block.page_number,
                block_id=block.id,
                parser_engine=parser_engine,
                confidence=0.82,
            )
            language_match = LANGUAGE_GOALS_PATTERN.match(line)
            if language_match:
                candidate = _language_goal_candidate(
                    current_unit,
                    language_match.group("goals"),
                    evidence,
                )
                if candidate and candidate.canonical_key not in seen:
                    seen.add(candidate.canonical_key)
                    candidates.append(candidate)
                continue

            if pending_activity_code:
                candidate = _activity_candidate(current_unit, pending_activity_code, line, evidence)
                pending_activity_code = None
                if candidate and candidate.canonical_key not in seen:
                    seen.add(candidate.canonical_key)
                    candidates.append(candidate)
                continue

            activity_match = ACTIVITY_CODE_PATTERN.match(line)
            if activity_match:
                code = activity_match.group("code").lower()
                title = activity_match.group("title")
                if title:
                    candidate = _activity_candidate(current_unit, code, title, evidence)
                    if candidate and candidate.canonical_key not in seen:
                        seen.add(candidate.canonical_key)
                        candidates.append(candidate)
                else:
                    pending_activity_code = code
                continue

            trailing_match = ACTIVITY_TRAILING_CODE_PATTERN.match(line)
            if trailing_match and _looks_like_activity_instruction(trailing_match.group("title")):
                candidate = _activity_candidate(
                    current_unit,
                    trailing_match.group("code").lower(),
                    trailing_match.group("title"),
                    evidence,
                )
                if candidate and candidate.canonical_key not in seen:
                    seen.add(candidate.canonical_key)
                    candidates.append(candidate)
                continue

            if sentence_counts.get(current_unit, 0) >= 8:
                continue
            candidate = _sentence_pattern_candidate(current_unit, line, evidence)
            if candidate and candidate.canonical_key not in seen:
                seen.add(candidate.canonical_key)
                sentence_counts[current_unit] = sentence_counts.get(current_unit, 0) + 1
                candidates.append(candidate)
    return tuple(candidates)


def _extract_appendix_knowledge(
    blocks: list[DocumentBlock],
    parser_engine: str,
) -> tuple[KnowledgeCandidate, ...]:
    candidates: list[KnowledgeCandidate] = []
    seen: set[str] = set()
    in_grammar = False
    in_pronunciation = False
    for block in blocks:
        for raw_line in block.text.splitlines():
            line = _clean_pdf_text(raw_line)
            if not line or _is_noise_line(line):
                continue
            if APPENDIX_STOP_PATTERN.match(line):
                in_grammar = False
                in_pronunciation = False
                continue
            if TAPESCRIPTS_SECTION_PATTERN.match(line):
                in_grammar = False
                in_pronunciation = False
                continue
            if GRAMMAR_SECTION_PATTERN.match(line):
                in_grammar = True
                in_pronunciation = False
                continue
            if PRONUNCIATION_SECTION_PATTERN.match(line):
                in_pronunciation = True
                in_grammar = False
                continue
            evidence = ExtractionEvidence(
                page_number=block.page_number,
                block_id=block.id,
                parser_engine=parser_engine,
                confidence=0.68,
            )
            candidate = None
            if in_pronunciation and _is_appendix_page(block.page_number):
                candidate = _pronunciation_candidate(line, evidence)
            if candidate is None and _should_try_grammar_candidate(
                page_number=block.page_number,
                in_grammar=in_grammar,
                in_pronunciation=in_pronunciation,
            ):
                candidate = _grammar_candidate(line, evidence)
            if candidate is None or candidate.canonical_key in seen:
                continue
            seen.add(candidate.canonical_key)
            candidates.append(candidate)
    return tuple(candidates)


def _extract_notes_knowledge(
    blocks: list[DocumentBlock],
    parser_engine: str,
) -> tuple[KnowledgeCandidate, ...]:
    candidates: list[KnowledgeCandidate] = []
    seen: set[str] = set()
    in_notes = False
    current_unit: str | None = None
    for block in blocks:
        for raw_line in block.text.splitlines():
            line = _clean_pdf_text(raw_line)
            if not line or _is_noise_line(line):
                continue
            if not in_notes and NOTES_SECTION_PATTERN.search(line) and _is_notes_page(block.page_number):
                in_notes = True
                line = NOTES_SECTION_PATTERN.sub("", line, count=1).strip(" -:·")
            if not in_notes:
                continue
            if TAPESCRIPTS_SECTION_PATTERN.match(line) or PRONUNCIATION_SECTION_PATTERN.match(line):
                return tuple(candidates)
            unit_match = INLINE_UNIT_PATTERN.search(line)
            if unit_match:
                current_unit = _normalize_inline_unit(unit_match.group("number"))
                line = line[unit_match.end() :].strip()
            if current_unit is None:
                continue
            note_match = NOTE_ITEM_PATTERN.search(line)
            if not note_match:
                continue
            number = int(note_match.group("number"))
            note_text = _compact_label(note_match.group("text"), max_length=180)
            if not _useful_note_text(note_text):
                continue
            evidence = ExtractionEvidence(
                page_number=block.page_number,
                block_id=block.id,
                parser_engine=parser_engine,
                confidence=0.84,
            )
            candidate = KnowledgeCandidate(
                canonical_key=f"text-note.{_slug(current_unit)}.note-{number}.{block.page_number or 0}",
                type="text_note",
                title=f"{current_unit} note {number}",
                summary=f"课文注释：{note_text}",
                page_number=block.page_number or 1,
                confidence=0.84,
                evidence=evidence,
            )
            if candidate.canonical_key in seen:
                continue
            seen.add(candidate.canonical_key)
            candidates.append(candidate)
    return tuple(candidates)


def _language_goal_candidate(
    unit_title: str,
    goals: str,
    evidence: ExtractionEvidence,
) -> KnowledgeCandidate | None:
    title = f"{unit_title} language goals"
    summary = _compact_label(f"教材语言目标：{goals}", max_length=180)
    return KnowledgeCandidate(
        canonical_key=f"text-note.{_slug(unit_title)}.language-goals.{evidence.page_number or 0}",
        type="text_note",
        title=title,
        summary=summary,
        page_number=evidence.page_number or 1,
        confidence=0.84,
        evidence=evidence,
    )


def _activity_candidate(
    unit_title: str,
    code: str,
    title: str,
    evidence: ExtractionEvidence,
) -> KnowledgeCandidate | None:
    cleaned = _compact_label(title, max_length=140)
    if not _looks_like_activity_instruction(cleaned):
        return None
    return KnowledgeCandidate(
        canonical_key=f"text-note.{_slug(unit_title)}.activity-{code}.{evidence.page_number or 0}",
        type="text_note",
        title=f"{unit_title} activity {code}",
        summary=f"教材活动：{cleaned}",
        page_number=evidence.page_number or 1,
        confidence=0.82,
        evidence=evidence,
    )


def _sentence_pattern_candidate(
    unit_title: str,
    line: str,
    evidence: ExtractionEvidence,
) -> KnowledgeCandidate | None:
    cleaned = _clean_knowledge_title(line)
    if not _looks_like_target_sentence(cleaned):
        return None
    return KnowledgeCandidate(
        canonical_key=f"sentence-pattern.{_slug(unit_title)}.{_slug(cleaned)}.{evidence.page_number or 0}",
        type="sentence_pattern",
        title=cleaned,
        summary=f"{unit_title} 重点句式：{cleaned}",
        page_number=evidence.page_number or 1,
        confidence=0.81,
        evidence=evidence,
    )


def _looks_like_activity_instruction(line: str) -> bool:
    if not line or len(line) > 180:
        return False
    lowered = line.casefold()
    return any(
        token in lowered
        for token in (
            "listen",
            "practice",
            "write",
            "read",
            "talk",
            "complete",
            "number",
            "match",
            "role-play",
            "choose",
            "ask",
            "answer",
            "look",
            "copy",
        )
    )


def _looks_like_target_sentence(line: str) -> bool:
    if not line or len(line) > 100:
        return False
    if re.search(r"[\u3400-\u9fff]", line):
        return False
    if _looks_like_activity_instruction(line):
        return False
    if not re.search(r"[A-Za-z]", line):
        return False
    if line.count(" ") > 14:
        return False
    lowered = line.casefold()
    if lowered.startswith(("page ", "starter unit", "unit ")):
        return False
    signal = any(mark in line for mark in ("?", "!", ".", "’", "'"))
    useful_words = any(
        token in lowered
        for token in (
            "what",
            "where",
            "when",
            "who",
            "why",
            "how",
            "i'm",
            "i’m",
            "it's",
            "it’s",
            "are",
            "is",
            "do",
            "does",
            "have",
            "like",
            "my",
            "your",
            "this",
            "that",
            "these",
            "those",
            "good morning",
            "good afternoon",
            "good evening",
            "hello",
            "hi",
        )
    )
    return signal and useful_words


def _grammar_candidate(line: str, evidence: ExtractionEvidence) -> KnowledgeCandidate | None:
    fragment_match = GRAMMAR_TOPIC_FRAGMENT_PATTERN.search(line)
    if fragment_match:
        title = fragment_match.group(0)
    else:
        title = ""
    match = GRAMMAR_HEADING_PATTERN.match(line)
    if title:
        pass
    elif not match:
        return None
    else:
        marker = match.group("marker")
        title = _compact_label(match.group("title"), max_length=90)
        if marker.isdigit() and not _looks_like_unmarked_grammar_heading(title):
            return None
    title = _clean_knowledge_title(title)
    if not _useful_knowledge_title(title):
        return None
    return KnowledgeCandidate(
        canonical_key=f"grammar.{_slug(title)}.{evidence.page_number or 0}",
        type="grammar",
        title=title,
        summary=f"教材语法附录知识点：{title}",
        page_number=evidence.page_number or 1,
        confidence=0.68,
        evidence=evidence,
        warnings=("appendix_heading",),
    )


def _pronunciation_candidate(line: str, evidence: ExtractionEvidence) -> KnowledgeCandidate | None:
    unit_match = UNIT_HEADING_PATTERN.match(line)
    if unit_match:
        unit_title = _normalize_unit_title(unit_match.group("title"))
        rest = _compact_label(unit_match.group("rest"), max_length=80)
        title = f"{unit_title} pronunciation"
        summary = f"教材语音附录知识点：{rest or unit_title}"
        canonical_key = f"pronunciation.{_slug(unit_title)}.{evidence.page_number or 0}"
    else:
        topic_match = PRONUNCIATION_TOPIC_PATTERN.search(line)
        if not topic_match:
            return None
        topic = _clean_knowledge_title(topic_match.group(0))
        title = f"Pronunciation: {topic}"
        summary = f"教材语音附录知识点：{_compact_label(line, max_length=140)}"
        canonical_key = f"pronunciation.{_slug(topic)}.{evidence.page_number or 0}"
    return KnowledgeCandidate(
        canonical_key=canonical_key,
        type="pronunciation",
        title=title,
        summary=summary,
        page_number=evidence.page_number or 1,
        confidence=0.66,
        evidence=evidence,
        warnings=("appendix_heading",),
    )


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
            if in_section and VOCABULARY_INDEX_PATTERN.search(line):
                return tuple(entries)
            if not in_section and VOCABULARY_INDEX_PATTERN.search(line):
                continue
            if VOCABULARY_SECTION_PATTERN.search(line):
                in_section = True
                buffer.clear()
                evidence_block = None
                continue
            if not line or _is_noise_line(line) or line.startswith("（注：") or line.startswith("在英式发音"):
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


def _extract_vocabulary_from_layout(artifact: DocumentParseArtifact) -> tuple[VocabularyCandidate, ...]:
    file_path = artifact.metadata.get("file_path") if isinstance(artifact.metadata, dict) else None
    if not isinstance(file_path, str):
        return ()
    path = Path(file_path)
    if path.suffix.casefold() != ".pdf" or not path.exists():
        return ()
    try:
        lines = _layout_lines_from_pdf(path)
    except Exception:
        return ()
    return _extract_vocabulary_from_layout_lines(lines, artifact.parser_engine)


def _layout_lines_from_pdf(path: Path) -> list[LayoutLine]:
    reader = PdfReader(path)
    lines: list[LayoutLine] = []
    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        midpoint = width / 2
        fragments: list[tuple[float, float, str]] = []

        def visitor(text: str, _cm: object, tm: object, _font_dict: object, _font_size: object) -> None:
            value = " ".join((text or "").split())
            if not value:
                return
            try:
                x = float(tm[4])  # type: ignore[index]
                y = float(tm[5])  # type: ignore[index]
            except (TypeError, ValueError, IndexError):
                return
            fragments.append((x, y, value))

        page.extract_text(visitor_text=visitor)
        for column, min_x, max_x in (
            (0, 0.0, midpoint + 6),
            (1, midpoint - 6, width + 1),
        ):
            column_fragments = [
                (x, y, text)
                for x, y, text in fragments
                if min_x <= x < max_x and not _is_layout_header_fragment(text, y)
            ]
            grouped = _group_layout_fragments(column_fragments)
            for index, (y, text) in enumerate(grouped, start=1):
                lines.append(
                    LayoutLine(
                        page_number=page_number,
                        column=column,
                        y=y,
                        text=text,
                        block_id=f"layout-p{page_number}-c{column + 1}-l{index}",
                    )
                )
    return sorted(lines, key=lambda item: (item.page_number, item.column, -item.y))


def _group_layout_fragments(
    fragments: list[tuple[float, float, str]],
    *,
    y_tolerance: float = 4.0,
) -> list[tuple[float, str]]:
    rows: list[list[tuple[float, float, str]]] = []
    for fragment in sorted(fragments, key=lambda item: -item[1]):
        for row in rows:
            if abs(row[0][1] - fragment[1]) <= y_tolerance:
                row.append(fragment)
                break
        else:
            rows.append([fragment])
    grouped: list[tuple[float, str]] = []
    for row in rows:
        y = sum(item[1] for item in row) / len(row)
        text = _clean_pdf_text(" ".join(item[2] for item in sorted(row, key=lambda item: item[0])))
        if text:
            grouped.append((y, text))
    return grouped


def _extract_vocabulary_from_layout_lines(
    lines: list[LayoutLine],
    parser_engine: str,
) -> tuple[VocabularyCandidate, ...]:
    entries: list[VocabularyCandidate] = []
    seen_keys: set[tuple[str, str]] = set()
    in_section = False
    current_unit: str | None = None
    unit_orders: dict[str, int] = {}
    for line in lines:
        text = _clean_pdf_text(line.text)
        if not text or _is_noise_line(text):
            continue
        if in_section and VOCABULARY_INDEX_PATTERN.search(text):
            return tuple(entries)
        if not in_section:
            if VOCABULARY_SECTION_PATTERN.search(text):
                in_section = True
            continue
        if VOCABULARY_SECTION_PATTERN.search(text) or text.startswith(("（注：", "在英式发音")):
            continue

        unit_title, rest = _layout_unit_and_rest(text, current_unit=current_unit)
        if unit_title:
            current_unit = unit_title
            unit_orders.setdefault(current_unit, 0)
            text = rest
            if not text:
                continue
        if current_unit is None:
            continue
        has_page_ref = bool(
            VOCABULARY_PAGE_REF_PATTERN.search(text)
            or VOCABULARY_ANY_PAGE_REF_PATTERN.search(text)
        )
        raw_line = _strip_vocabulary_page_ref(text)
        if not _looks_like_layout_vocabulary_entry(raw_line, has_page_ref=has_page_ref):
            continue
        next_order = unit_orders[current_unit] + 1
        entry = _parse_vocabulary_line(
            current_unit=current_unit,
            raw_line=raw_line,
            unit_order=next_order,
            block=DocumentBlock(
                id=line.block_id,
                page_number=line.page_number,
                type="line",
                text=line.text,
                reading_order=len(entries),
                confidence=0.82,
                source="pdf-layout",
            ),
            parser_engine=parser_engine,
        )
        if entry is None:
            continue
        seen_key = (entry.unit_title, entry.canonical_expression)
        if seen_key in seen_keys:
            continue
        seen_keys.add(seen_key)
        unit_orders[current_unit] = next_order
        entries.append(entry)
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
    if not _is_valid_layout_expression(expression, canonical):
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


def _layout_unit_and_rest(line: str, *, current_unit: str | None) -> tuple[str | None, str]:
    match = LAYOUT_UNIT_PATTERN.match(line.strip())
    if not match:
        return None, line
    prefix = match.group("prefix")
    raw_number = match.group("number")
    rest = match.group("rest").strip(" :·—-")
    if raw_number is None:
        if current_unit is None and prefix.casefold() == "unit":
            return "Unit 1", rest
        return None, line
    number = "5" if raw_number in {"$", "S", "s"} else raw_number
    title = f"{'Starter Unit' if prefix.casefold().startswith('starter') else 'Unit'} {int(number)}"
    return title, rest


def _strip_vocabulary_page_ref(value: str) -> str:
    return VOCABULARY_ANY_PAGE_REF_PATTERN.sub("", value).strip(" ;,，。")


def _looks_like_layout_vocabulary_entry(value: str, *, has_page_ref: bool) -> bool:
    if len(value) < 2 or len(value) > 140:
        return False
    if not re.match(r"[A-Za-z][A-Za-z0-9 .’'()/\-]*", value):
        return False
    lowered = value.casefold()
    if lowered.startswith(("words and expressions", "vocabulary index", "name list")):
        return False
    has_structured_marker = bool(
        PHONETIC_PATTERN.match(value)
        or PART_OF_SPEECH_PATTERN.search(value)
        or re.search(r"[\u3400-\u9fff]", value)
    )
    return has_structured_marker or has_page_ref


def _is_layout_header_fragment(text: str, y: float) -> bool:
    if y < 690:
        return False
    normalized = text.casefold()
    return "words" in normalized or "expressions" in normalized or normalized in {"and", "in", "each", "unit"}


def _normalize_expression(value: str) -> str:
    expression = " ".join(value.split()).strip(" ·—-")
    replacements = {
        "a/f_ternoon": "afternoon",
        "a/f_ter": "after",
        "alittle": "a little",
        "getto": "get to",
        "getup": "get up",
        "goalong": "go along",
        "inthe": "in the",
        "ittle": "little",
        "milka cow": "milk a cow",
        "quite alot": "quite a lot",
        "read anewspaper": "read a newspaper",
        "talll": "tall",
        "take a message fH fas": "take a message",
        "take one’s order 3K": "take one's order",
        "telephone/phone number": "telephone number",
        "feed chickens i": "feed chickens",
        "tide a bike": "ride a bike",
        "tide a horse": "ride a horse",
        "twel/f_th": "twelfth",
        "wouldlike": "would like",
        "/T_hursday": "Thursday",
        "P .E.": "P.E.",
        "P. M .": "P.M.",
        "To m": "Tom",
        "burg er": "burger",
    }
    for source, target in replacements.items():
        expression = expression.replace(source, target)
    expression = re.sub(r"\bY\s+ou", "You", expression)
    expression = re.sub(r"(\.\.\.)\s+.*$", r"\1", expression)
    return expression.replace("_", "").strip(" （(").strip()


def _is_valid_layout_expression(expression: str, canonical: str) -> bool:
    if not canonical or not re.search(r"[a-z]", canonical) or len(expression) > 100:
        return False
    if canonical in {
        "adj",
        "adv",
        "art",
        "conj",
        "expression",
        "expressions",
        "interj",
        "n",
        "num",
        "page",
        "pb",
        "prep",
        "pron",
        "unit",
        "v",
        "words",
    }:
        return False
    allowed_short = {"am", "be", "do", "go", "if", "is", "mr", "ms", "no", "of", "ok", "or", "tv", "up"}
    if re.fullmatch(r"[a-z]{1,2}", canonical) and canonical not in allowed_short:
        return False
    if re.match(r"^[a-z]\s+", canonical):
        return False
    if ";" in expression:
        return False
    if re.search(r"\bp[.\-]?\s*[a-z0-9]+\b", canonical):
        return False
    if re.search(r"\bunit\b", canonical):
        return False
    letters = [character for character in expression if character.isalpha()]
    uppercase = [character for character in letters if character.isupper()]
    if letters and len(letters) >= 5 and len(uppercase) / len(letters) > 0.55 and "." not in expression:
        return False
    return True


def _canonical_expression(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "candidate"


def _clean_pdf_text(value: str) -> str:
    return " ".join(value.replace("\u2003", " ").split()).strip()


def _is_noise_line(value: str) -> bool:
    return bool(NOISE_LINE_PATTERN.fullmatch(value.strip()))


def _is_appendix_page(page_number: int | None) -> bool:
    return page_number is None or page_number >= 98


def _is_notes_page(page_number: int | None) -> bool:
    return page_number is None or page_number >= 70


def _is_likely_grammar_page(page_number: int | None) -> bool:
    return page_number is not None and 108 <= page_number <= 130


def _should_try_grammar_candidate(
    *,
    page_number: int | None,
    in_grammar: bool,
    in_pronunciation: bool,
) -> bool:
    if not _is_appendix_page(page_number):
        return False
    if in_grammar:
        return True
    if page_number is None:
        return False
    if in_pronunciation and page_number < 120:
        return False
    return _is_likely_grammar_page(page_number)


def _unit_sort_key(title: str, page_number: int) -> tuple[int, int, int]:
    match = VOCABULARY_UNIT_PATTERN.match(title)
    if not match:
        return (2, page_number, 999)
    is_starter = match.group(1).casefold().startswith("starter")
    return (0 if is_starter else 1, int(match.group(2)), page_number)


def _clean_knowledge_title(value: str) -> str:
    value = _clean_pdf_text(value).strip(" ：:")
    value = re.sub(r"^[工IⅤVX]+\s*[.、]?\s*[“\"']?", "", value).strip()
    for separator in (" ：", "：", ": "):
        head = value.split(separator, 1)[0].strip()
        if 3 <= len(head) <= 100:
            value = head
            break
    return re.sub(r"\s+", " ", value)


def _useful_knowledge_title(value: str) -> bool:
    if len(value) < 3 or len(value) > 100:
        return False
    if _is_noise_line(value):
        return False
    return bool(re.search(r"[A-Za-z\u3400-\u9fff]", value))


def _looks_like_unmarked_grammar_heading(value: str) -> bool:
    cleaned = _clean_knowledge_title(value)
    if len(cleaned) > 80:
        return False
    return bool(re.search(r"[（(][^）)]{2,60}[）)]", cleaned))


def _normalize_inline_unit(value: str) -> str:
    normalized = "5" if value.casefold() == "s" else value
    return f"Unit {int(normalized)}"


def _useful_note_text(value: str) -> bool:
    if len(value) < 8:
        return False
    if value.casefold().startswith(("section ", "conversation ")):
        return False
    return bool(re.search(r"[A-Za-z\u3400-\u9fff]", value))
