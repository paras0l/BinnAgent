import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource

UNIT_PATTERN = re.compile(r"(?im)^\s*((?:Starter\s+)?Unit\s+\d+)\s*$\s*^\s*([^\n]{3,80})\s*$")


@dataclass(frozen=True)
class ParsedUnit:
    title: str
    subtitle: str
    page_number: int


@dataclass(frozen=True)
class ParsedTextbook:
    page_count: int
    units: tuple[ParsedUnit, ...]
    text_char_count: int


@dataclass(frozen=True)
class ParsedVocabularyEntry:
    unit_title: str
    expression: str
    canonical_expression: str
    phonetic: str | None
    meaning: str
    lesson_page: str
    pdf_page: int
    entry_kind: str
    confidence: float


VOCABULARY_HEADING = "Words and Expressions in Each Unit"
VOCABULARY_INDEX_HEADING = "Vocabulary Index"
VOCABULARY_UNIT_PATTERN = re.compile(r"^(Starter\s+Unit|Unit)\s+(\d+)\s*$", re.IGNORECASE)
VOCABULARY_PAGE_REF_PATTERN = re.compile(r"\s+p\.(S?\d+(?:[–-]S?\d+)?)\s*$", re.IGNORECASE)
PHONETIC_PATTERN = re.compile(
    r"^(?P<expression>.+?)\s+(?P<phonetic>/[^/]+/(?:\s*,\s*/[^/]+/)?)\s*(?P<rest>.*)$"
)
PART_OF_SPEECH_PATTERN = re.compile(
    r"\b(?:adj|adv|art|conj|interj|modal\s+v|n|num|prep|pron|v)\.(?:\s*&\s*(?:adj|adv|n|pron|v)\.)?",
    re.IGNORECASE,
)


PEP_GRADE7_LOWER_UNITS: tuple[ParsedUnit, ...] = (
    ParsedUnit("Unit 1", "Can you play the guitar?", 1),
    ParsedUnit("Unit 2", "What time do you go to school?", 7),
    ParsedUnit("Unit 3", "How do you get to school?", 13),
    ParsedUnit("Unit 4", "Don't eat in class.", 19),
    ParsedUnit("Unit 5", "Why do you like pandas?", 25),
    ParsedUnit("Unit 6", "I'm watching TV.", 31),
    ParsedUnit("Unit 7", "It's raining!", 37),
    ParsedUnit("Unit 8", "Is there a post office near here?", 43),
    ParsedUnit("Unit 9", "What does he look like?", 49),
    ParsedUnit("Unit 10", "I'd like some noodles.", 55),
    ParsedUnit("Unit 11", "How was your school trip?", 61),
    ParsedUnit("Unit 12", "What did you do last weekend?", 67),
)

PEP_GRADE7_LOWER_KNOWLEDGE: dict[str, tuple[str, str, str, str]] = {
    "Unit 1": ("grammar.modal-can", "grammar", "Modal verb can", "用 can 表达能力。"),
    "Unit 2": ("phrase.get-up", "phrase", "get up", "表示起床这一日常活动。"),
    "Unit 3": (
        "pattern.how-get-school",
        "sentence_pattern",
        "How do you get to school?",
        "询问交通方式。",
    ),
    "Unit 4": ("grammar.imperatives", "grammar", "Imperatives", "使用祈使句表达规则。"),
    "Unit 5": ("grammar.because", "grammar", "Because clauses", "使用 because 说明原因。"),
    "Unit 6": (
        "grammar.present-progressive-1",
        "grammar",
        "Present progressive tense (I)",
        "描述正在进行的活动。",
    ),
    "Unit 7": (
        "pattern.hows-weather",
        "sentence_pattern",
        "How's the weather?",
        "询问天气情况。",
    ),
    "Unit 8": (
        "grammar.there-be",
        "grammar",
        "There be structure",
        "描述某处存在的人或事物。",
    ),
    "Unit 9": ("phrase.look-like", "phrase", "look like", "询问或描述外貌。"),
    "Unit 10": (
        "grammar.would-like",
        "grammar",
        "would like",
        "礼貌表达想要的食物。",
    ),
    "Unit 11": (
        "grammar.simple-past-1",
        "grammar",
        "Simple past tense (I)",
        "谈论过去发生的事情。",
    ),
    "Unit 12": (
        "grammar.simple-past-2",
        "grammar",
        "Simple past tense (II)",
        "使用特殊疑问句谈论周末活动。",
    ),
}

PEP_GRADE7_UPPER_KNOWLEDGE: dict[str, tuple[str, str, str, str]] = {
    "Starter Unit 2": (
        "pattern.whats-this-english",
        "sentence_pattern",
        "What's this in English?",
        "询问某个物品用英语怎么表达。",
    ),
    "Starter Unit 3": (
        "pattern.what-color",
        "sentence_pattern",
        "What color is it?",
        "询问并描述物品的颜色。",
    ),
    "Unit 1": ("grammar.be-verbs", "grammar", "am / is / are", "使用 be 动词介绍自己和他人。"),
    "Unit 2": (
        "grammar.demonstratives-family",
        "grammar",
        "this / that / these / those",
        "使用指示代词介绍家人。",
    ),
    "Unit 3": (
        "grammar.possessive-pronouns",
        "grammar",
        "Possessive pronouns",
        "使用物主代词询问物品归属。",
    ),
    "Unit 4": (
        "grammar.where-questions",
        "grammar",
        "Where questions",
        "使用 where 询问物品的位置。",
    ),
    "Unit 5": (
        "grammar.have-has",
        "grammar",
        "have / has",
        "使用 have 和 has 谈论拥有的物品。",
    ),
    "Unit 6": (
        "grammar.like-present",
        "grammar",
        "like in the simple present",
        "使用一般现在时表达食物喜好。",
    ),
    "Unit 7": (
        "pattern.how-much",
        "sentence_pattern",
        "How much ...?",
        "询问商品价格并进行购物交流。",
    ),
    "Unit 8": (
        "grammar.when-questions",
        "grammar",
        "When questions",
        "使用 when 询问日期和生日。",
    ),
    "Unit 9": (
        "pattern.favorite-subject",
        "sentence_pattern",
        "What's your favorite subject?",
        "询问并说明最喜欢的学科及原因。",
    ),
}


def _parse_pdf(path: Path) -> ParsedTextbook:
    reader = PdfReader(path)
    units: list[ParsedUnit] = []
    seen: set[str] = set()
    text_char_count = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text_char_count += len(text)
        for match in UNIT_PATTERN.finditer(text):
            title = " ".join(match.group(1).split())
            subtitle = " ".join(match.group(2).split()).strip(" ·—-")
            key = title.casefold()
            if key in seen or subtitle.lower() in {"contents", "topics", "functions"}:
                continue
            seen.add(key)
            units.append(ParsedUnit(title=title, subtitle=subtitle, page_number=page_number))
    units.sort(
        key=lambda unit: (0 if unit.title.lower().startswith("starter") else 1, unit.page_number)
    )
    return ParsedTextbook(
        page_count=len(reader.pages),
        units=tuple(units[:20]),
        text_char_count=text_char_count,
    )


def _normalize_unit_title(value: str) -> str:
    match = VOCABULARY_UNIT_PATTERN.fullmatch(" ".join(value.split()))
    if not match:
        return " ".join(value.split())
    prefix = "Starter Unit" if match.group(1).lower().startswith("starter") else "Unit"
    return f"{prefix} {int(match.group(2))}"


def _normalize_expression(value: str) -> str:
    expression = " ".join(value.split()).strip(" ·—-")
    expression = expression.replace("a/f_ternoon", "afternoon")
    expression = expression.replace("_", "")
    return expression


def _canonical_expression(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def _entry_kind(expression: str) -> str:
    if len(expression) <= 8 and expression.replace(".", "").isupper():
        return "abbreviation"
    if " " in expression or "/" in expression:
        return "phrase"
    if expression[:1].isupper():
        return "proper_noun"
    return "word"


def _parse_vocabulary_chunk(
    unit_title: str,
    pdf_page: int,
    chunk: str,
    lesson_page: str,
) -> ParsedVocabularyEntry | None:
    normalized = " ".join(chunk.split())
    phonetic_match = PHONETIC_PATTERN.match(normalized)
    phonetic: str | None = None
    if phonetic_match:
        expression = _normalize_expression(phonetic_match.group("expression"))
        phonetic = phonetic_match.group("phonetic").strip()
        rest = phonetic_match.group("rest").strip()
    else:
        pos_match = PART_OF_SPEECH_PATTERN.search(normalized)
        cjk_match = re.search(r"[\u3400-\u9fff]", normalized)
        split_at = (
            pos_match.start() if pos_match else cjk_match.start() if cjk_match else len(normalized)
        )
        expression = _normalize_expression(normalized[:split_at])
        rest = normalized[split_at:].strip()
    canonical = _canonical_expression(expression)
    if not canonical or not re.search(r"[a-z]", canonical) or len(expression) > 100:
        return None
    meaning = PART_OF_SPEECH_PATTERN.sub("", rest, count=1).strip(" ;；")
    confidence = 0.98 if phonetic and meaning else 0.92 if meaning else 0.72
    return ParsedVocabularyEntry(
        unit_title=unit_title,
        expression=expression,
        canonical_expression=canonical,
        phonetic=phonetic,
        meaning=meaning or "教材词表收录词汇",
        lesson_page=lesson_page,
        pdf_page=pdf_page,
        entry_kind=_entry_kind(expression),
        confidence=confidence,
    )


def _parse_unit_vocabulary(reader: PdfReader) -> tuple[ParsedVocabularyEntry, ...]:
    start_threshold = int(len(reader.pages) * 0.7)
    in_vocabulary_section = False
    current_unit: str | None = None
    buffer: list[str] = []
    entries: list[ParsedVocabularyEntry] = []
    ignored_lines = {"Page PB", VOCABULARY_HEADING, "9594", "9796", "9998", "101100", "103102"}

    for pdf_page, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not in_vocabulary_section:
            if pdf_page < start_threshold or VOCABULARY_HEADING not in text:
                continue
            in_vocabulary_section = True
        if VOCABULARY_INDEX_HEADING in text:
            break

        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if (
                not line
                or line in ignored_lines
                or line.isdigit()
                or line.startswith("（注：")
                or line.startswith("在英式发音")
                or line.startswith(VOCABULARY_HEADING)
            ):
                continue
            unit_match = VOCABULARY_UNIT_PATTERN.fullmatch(line)
            if unit_match:
                buffer.clear()
                current_unit = _normalize_unit_title(line)
                continue
            if current_unit is None:
                continue
            buffer.append(line)
            combined = " ".join(buffer)
            page_ref_match = VOCABULARY_PAGE_REF_PATTERN.search(combined)
            if not page_ref_match:
                continue
            entry = _parse_vocabulary_chunk(
                current_unit,
                pdf_page,
                combined[: page_ref_match.start()],
                page_ref_match.group(1),
            )
            if entry is not None:
                entries.append(entry)
            buffer.clear()
    return tuple(entries)


def _known_knowledge(source_id: uuid.UUID, node_id: uuid.UUID, title: str) -> list[KnowledgePoint]:
    lower_item = PEP_GRADE7_LOWER_KNOWLEDGE.get(title)
    if lower_item:
        key, point_type, point_title, summary = lower_item
        return [
            KnowledgePoint(
                source_id=source_id,
                curriculum_node_id=node_id,
                canonical_key=f"{key}.{str(source_id)[:8]}",
                type=point_type,
                title=point_title,
                summary=summary,
                source_page="目录",
                difficulty=0.3,
                status="draft",
                content={"origin": "verified_toc_fallback", "requires_review": True},
            )
        ]
    upper_item = PEP_GRADE7_UPPER_KNOWLEDGE.get(title)
    if upper_item:
        key, point_type, point_title, summary = upper_item
        return [
            KnowledgePoint(
                source_id=source_id,
                curriculum_node_id=node_id,
                canonical_key=f"{key}.{str(source_id)[:8]}",
                type=point_type,
                title=point_title,
                summary=summary,
                source_page="目录",
                difficulty=0.3,
                status="draft",
                content={"origin": "verified_toc_fallback", "requires_review": True},
            )
        ]
    if title.casefold() != "starter unit 1":
        return []
    values = [
        ("phrase.good-morning", "phrase", "Good morning!", "用于早晨向他人问好。", "P.2"),
        ("pattern.how-are-you", "sentence_pattern", "How are you?", "用于询问对方的近况。", "P.2"),
        (
            "vocabulary.letters-a-h",
            "vocabulary",
            "Letters A–H",
            "字母 A 到 H 的读音与书写。",
            "P.3–4",
        ),
        (
            "pattern.im-fine-thanks",
            "sentence_pattern",
            "I'm fine, thanks.",
            "用于回复对方的问候。",
            "P.2",
        ),
    ]
    return [
        KnowledgePoint(
            source_id=source_id,
            curriculum_node_id=node_id,
            canonical_key=f"{key}.{str(source_id)[:8]}",
            type=point_type,
            title=point_title,
            summary=summary,
            source_page=page,
            difficulty=0.2,
            status="draft",
            content={"origin": "rule_based", "requires_review": True},
        )
        for key, point_type, point_title, summary, page in values
    ]


async def process_uploaded_textbook(db: AsyncSession, source: KnowledgeSource) -> ParsedTextbook:
    if not source.object_key:
        raise ValueError("Knowledge source has no stored PDF")
    path = Path(source.object_key)
    parsed = await asyncio.to_thread(_parse_pdf, path)
    vocabulary_entries = await asyncio.to_thread(lambda: _parse_unit_vocabulary(PdfReader(path)))
    used_toc_fallback = False
    if not parsed.units and "七年级下册" in source.filename:
        parsed = ParsedTextbook(
            page_count=parsed.page_count,
            units=PEP_GRADE7_LOWER_UNITS,
            text_char_count=parsed.text_char_count,
        )
        used_toc_fallback = True

    await db.execute(delete(KnowledgePoint).where(KnowledgePoint.source_id == source.id))
    await db.execute(delete(CurriculumNode).where(CurriculumNode.source_id == source.id))

    nodes: list[CurriculumNode] = []
    for ordinal, unit in enumerate(parsed.units, start=1):
        node = CurriculumNode(
            source_id=source.id,
            node_type="unit",
            title=unit.title,
            subtitle=unit.subtitle,
            ordinal=ordinal,
            start_page=str(unit.page_number),
            end_page=str(unit.page_number),
            estimated_minutes=20,
            learning_objectives=[],
        )
        db.add(node)
        nodes.append(node)
    await db.flush()

    knowledge_points: list[KnowledgePoint] = []
    for node in nodes:
        knowledge_points.extend(_known_knowledge(source.id, node.id, node.title))
    nodes_by_title = {_normalize_unit_title(node.title): node for node in nodes}
    seen_vocabulary_keys: set[tuple[uuid.UUID, str]] = set()
    for entry in vocabulary_entries:
        node = nodes_by_title.get(entry.unit_title)
        if node is None:
            continue
        duplicate_key = (node.id, entry.canonical_expression)
        if duplicate_key in seen_vocabulary_keys:
            continue
        seen_vocabulary_keys.add(duplicate_key)
        slug = re.sub(r"[^a-z0-9]+", "-", entry.canonical_expression).strip("-")
        knowledge_points.append(
            KnowledgePoint(
                source_id=source.id,
                curriculum_node_id=node.id,
                canonical_key=f"vocabulary.{slug}.{str(source.id)[:8]}.{node.ordinal}",
                type="vocabulary",
                title=entry.expression,
                summary=entry.meaning,
                source_page=f"P.{entry.lesson_page}",
                difficulty=0.2,
                status="draft",
                content={
                    "origin": "unit_wordlist_parser",
                    "role": "unit_wordlist",
                    "lemma": entry.canonical_expression,
                    "entry_kind": entry.entry_kind,
                    "phonetic": entry.phonetic,
                    "definitions_zh": [entry.meaning],
                    "examples": [],
                    "lesson_printed_page": entry.lesson_page,
                    "evidence_pdf_page": entry.pdf_page,
                    "parser_confidence": entry.confidence,
                    "requires_review": entry.confidence < 0.85,
                },
            )
        )
    for point in knowledge_points:
        db.add(point)

    source.page_count = parsed.page_count
    source.unit_count = len(nodes)
    source.knowledge_count = len(knowledge_points)
    source.status = "review_required"
    source.metadata_ = {
        "stage": "validated",
        "text_char_count": parsed.text_char_count,
        "parser": "pypdf+unit-wordlist-v2",
        "vocabulary_entry_count": len(vocabulary_entries),
        "toc_fallback": used_toc_fallback,
        "warning": None if nodes else "未识别到目录结构，需要人工校对",
    }
    await db.flush()
    return parsed


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    return result.scalar_one_or_none()
