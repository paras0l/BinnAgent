import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.parser_profiles import profile_for_source
from src.knowledge.parser_report import build_parser_report
from src.knowledge.rag import build_chunks
from src.models.knowledge import CurriculumNode, KnowledgeChunk, KnowledgePoint, KnowledgeSource
from src.providers.router import router as model_router

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
    unit_order: int
    raw_line: str
    confidence: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedAppendixSection:
    unit_title: str | None
    printed_pages: str
    pdf_pages: tuple[int, ...]
    text: str


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

UPPER_UNIT_MARKER_PATTERN = re.compile(r"\b(Starter\s+Unit|Unit)\s+([1-9])\b", re.I)

GRADE7_UPPER_NODE_TITLES = (
    "Starter Unit 1",
    "Starter Unit 2",
    "Starter Unit 3",
    "Unit 1",
    "Unit 2",
    "Unit 3",
    "Unit 4",
    "Unit 5",
    "Unit 6",
    "Unit 7",
    "Unit 8",
    "Unit 9",
)

# The appendix is organized by grammar category rather than unit. These mappings
# follow the examples and target language in the unit pages, so learners see each
# reference topic where it is first or most directly taught.
GRADE7_UPPER_GRAMMAR_TOPICS: tuple[dict[str, object], ...] = (
    {
        "key": "parts-of-speech",
        "title": "词类（Parts of Speech）",
        "summary": "识别名词、代词、数词、动词、形容词、副词、冠词、介词、连词和感叹词。",
        "page": "85",
        "primary": "Starter Unit 1",
        "related": list(GRADE7_UPPER_NODE_TITLES),
    },
    {
        "key": "nouns-countability",
        "title": "可数名词与不可数名词",
        "summary": "区分可数名词和不可数名词，并正确使用单复数形式。",
        "page": "85–86",
        "primary": "Unit 6",
        "related": ["Unit 2", "Unit 3", "Unit 6", "Unit 7"],
    },
    {
        "key": "noun-plurals",
        "title": "名词复数的构成与读音",
        "summary": "掌握 -s/-es、辅音字母+y 等复数规则、读音及常见不规则复数。",
        "page": "85–86",
        "primary": "Unit 2",
        "related": ["Unit 2", "Unit 3", "Unit 6", "Unit 7"],
    },
    {
        "key": "noun-possessive",
        "title": "名词所有格（Possessive Case）",
        "summary": "使用 ’s、’ 表达所属关系。",
        "page": "86",
        "primary": "Unit 8",
        "related": ["Unit 2", "Unit 8"],
    },
    {
        "key": "articles",
        "title": "冠词（Articles）",
        "summary": "根据语境使用 the、a/an 或零冠词。",
        "page": "87",
        "primary": "Starter Unit 2",
        "related": ["Starter Unit 2", "Unit 3", "Unit 5", "Unit 6"],
    },
    {
        "key": "personal-pronouns",
        "title": "人称代词（Personal Pronouns）",
        "summary": "区分人称代词的主格和宾格，并保持人称与数一致。",
        "page": "87",
        "primary": "Unit 1",
        "related": ["Unit 1", "Unit 2", "Unit 5", "Unit 9"],
    },
    {
        "key": "possessive-pronouns",
        "title": "物主代词（Possessive Pronouns）",
        "summary": "区分形容词性物主代词与名词性物主代词。",
        "page": "87–88",
        "primary": "Unit 3",
        "related": ["Unit 1", "Unit 3", "Unit 4"],
    },
    {
        "key": "demonstratives",
        "title": "指示代词（Demonstrative Pronouns）",
        "summary": "根据远近和单复数使用 this、that、these、those。",
        "page": "88",
        "primary": "Unit 2",
        "related": ["Unit 2", "Unit 3", "Unit 7"],
    },
    {
        "key": "cardinal-numbers",
        "title": "基数词（Cardinal Numbers）",
        "summary": "使用基数词表达号码、数量、年龄和价格。",
        "page": "88",
        "primary": "Unit 1",
        "related": ["Unit 1", "Unit 5", "Unit 7", "Unit 8"],
    },
    {
        "key": "ordinal-numbers",
        "title": "序数词（Ordinal Numbers）",
        "summary": "掌握序数词的拼写与缩写，并用于日期表达。",
        "page": "89",
        "primary": "Unit 8",
        "related": ["Unit 8"],
    },
    {
        "key": "simple-present-be",
        "title": "一般现在时：be 动词",
        "summary": "使用 am/is/are 构成肯定句、否定句、疑问句和简略答语。",
        "page": "89–90",
        "primary": "Unit 1",
        "related": ["Unit 1", "Unit 2", "Unit 4", "Unit 8", "Unit 9"],
    },
    {
        "key": "simple-present-verbs",
        "title": "一般现在时：实义动词",
        "summary": "掌握第三人称单数变化以及 do/does 构成的否定句和疑问句。",
        "page": "90–91",
        "primary": "Unit 5",
        "related": ["Unit 5", "Unit 6", "Unit 9"],
    },
    {
        "key": "prepositions",
        "title": "介词（Prepositions）",
        "summary": "掌握本册 about、after、at、for、from、in、of、on、under、with 等常用介词短语。",
        "page": "91–92",
        "primary": "Unit 4",
        "related": ["Starter Unit 2", "Unit 2", "Unit 3", "Unit 4", "Unit 7", "Unit 8", "Unit 9"],
    },
    {
        "key": "sentence-types",
        "title": "句子种类（Sentence Types）",
        "summary": "区分陈述句、疑问句、祈使句和感叹句的用途与基本结构。",
        "page": "92",
        "primary": "Starter Unit 1",
        "related": list(GRADE7_UPPER_NODE_TITLES),
    },
    {
        "key": "yes-no-questions",
        "title": "一般疑问句（Yes/No Questions）",
        "summary": "用 be、do/does 提问，并使用 Yes/No 简略回答。",
        "page": "93",
        "primary": "Unit 3",
        "related": ["Unit 1", "Unit 3", "Unit 5", "Unit 6"],
    },
    {
        "key": "wh-questions",
        "title": "特殊疑问句（Wh- Questions）",
        "summary": "使用 what、who、where、when、why、how 获取具体信息。",
        "page": "93",
        "primary": "Unit 9",
        "related": [
            "Starter Unit 2",
            "Starter Unit 3",
            "Unit 1",
            "Unit 2",
            "Unit 4",
            "Unit 7",
            "Unit 8",
            "Unit 9",
        ],
    },
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
    replacements = {
        "a/f_ternoon": "afternoon",
        "a/f_ter": "after",
        "twel/f_th": "twelfth",
        "/T_hursday": "Thursday",
        "P .E.": "P.E.",
        "P. M .": "P.M.",
        "To m": "Tom",
        "burg er": "burger",
    }
    for source, target in replacements.items():
        expression = expression.replace(source, target)
    expression = re.sub(r"\bY\s+ou", "You", expression)
    expression = expression.replace("_", "")
    return expression.rstrip(" （").strip()


def _canonical_expression(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def _parse_vocabulary_chunk(
    unit_title: str,
    chunk: str,
    unit_order: int,
) -> ParsedVocabularyEntry | None:
    normalized = " ".join(chunk.split())
    phonetic_match = PHONETIC_PATTERN.match(normalized)
    if phonetic_match:
        expression = _normalize_expression(phonetic_match.group("expression"))
    else:
        pos_match = PART_OF_SPEECH_PATTERN.search(normalized)
        cjk_match = re.search(r"[\u3400-\u9fff]", normalized)
        split_at = (
            pos_match.start() if pos_match else cjk_match.start() if cjk_match else len(normalized)
        )
        expression = _normalize_expression(normalized[:split_at])
    canonical = _canonical_expression(expression)
    if not canonical or not re.search(r"[a-z]", canonical) or len(expression) > 100:
        return None
    warnings: list[str] = []
    confidence = 0.92
    if not phonetic_match:
        confidence -= 0.12
        warnings.append("missing_phonetic")
    if re.search(r"\b(?:Page PB|9594|101100)\b", normalized):
        confidence -= 0.35
        warnings.append("dirty_pdf_token")
    return ParsedVocabularyEntry(
        unit_title=unit_title,
        expression=expression,
        canonical_expression=canonical,
        unit_order=unit_order,
        raw_line=normalized,
        confidence=max(0, confidence),
        warnings=tuple(warnings),
    )


def _parse_unit_vocabulary(reader: PdfReader) -> tuple[ParsedVocabularyEntry, ...]:
    start_threshold = int(len(reader.pages) * 0.7)
    in_vocabulary_section = False
    current_unit: str | None = None
    buffer: list[str] = []
    entries: list[ParsedVocabularyEntry] = []
    unit_orders: dict[str, int] = {}
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
                unit_orders.setdefault(current_unit, 0)
                continue
            if current_unit is None:
                continue
            buffer.append(line)
            combined = " ".join(buffer)
            page_ref_match = VOCABULARY_PAGE_REF_PATTERN.search(combined)
            if not page_ref_match:
                continue
            next_order = unit_orders[current_unit] + 1
            entry = _parse_vocabulary_chunk(
                current_unit, combined[: page_ref_match.start()], next_order
            )
            if entry is not None:
                entries.append(entry)
                unit_orders[current_unit] = next_order
            buffer.clear()
    return tuple(entries)


def _clean_appendix_text(text: str, heading: str) -> str:
    text = text.replace("Page PB", " ").replace(heading, " ")
    text = re.sub(r"(?<![A-Za-z])\d{2,3}(?![A-Za-z])", " ", text, count=1)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _appendix_pages(
    reader: PdfReader,
    heading: str,
    stop_heading: str,
) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    active = False
    start_threshold = int(len(reader.pages) * 0.5)
    for pdf_page, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not active:
            if pdf_page < start_threshold or heading not in text:
                continue
            active = True
        if stop_heading in text:
            break
        pages.append((pdf_page, _clean_appendix_text(text, heading)))
    return pages


def _group_appendix_by_unit(
    pages: list[tuple[int, str]],
) -> tuple[ParsedAppendixSection, ...]:
    fragments: dict[str | None, list[str]] = {None: []}
    evidence: dict[str | None, set[int]] = {None: set()}
    current_unit: str | None = None
    for pdf_page, text in pages:
        matches = list(UPPER_UNIT_MARKER_PATTERN.finditer(text))
        cursor = 0
        for match in matches:
            prefix = text[cursor : match.start()].strip()
            if prefix:
                fragments.setdefault(current_unit, []).append(prefix)
                evidence.setdefault(current_unit, set()).add(pdf_page)
            current_unit = _normalize_unit_title(match.group(0))
            cursor = match.end()
        suffix = text[cursor:].strip()
        if suffix:
            fragments.setdefault(current_unit, []).append(suffix)
            evidence.setdefault(current_unit, set()).add(pdf_page)

    result: list[ParsedAppendixSection] = []
    for unit_title, values in fragments.items():
        if not values:
            continue
        pdf_pages = tuple(sorted(evidence[unit_title]))
        # In this edition appendix printed pages are consistently PDF page - 23.
        printed = tuple(page - 23 for page in pdf_pages)
        page_label = str(printed[0]) if len(printed) == 1 else f"{printed[0]}–{printed[-1]}"
        result.append(
            ParsedAppendixSection(
                unit_title=unit_title,
                printed_pages=page_label,
                pdf_pages=pdf_pages,
                text=" ".join(values),
            )
        )
    return tuple(result)


def _parse_notes_on_the_text(reader: PdfReader) -> tuple[ParsedAppendixSection, ...]:
    pages = _appendix_pages(reader, "Notes on the Text", "Tapescripts")
    return tuple(section for section in _group_appendix_by_unit(pages) if section.unit_title)


def _parse_pronunciation(reader: PdfReader) -> tuple[ParsedAppendixSection, ...]:
    pages = _appendix_pages(reader, "Pronunciation", "Grammar")
    return _group_appendix_by_unit(pages)


def _appendix_knowledge(
    source_id: uuid.UUID,
    nodes_by_title: dict[str, CurriculumNode],
    notes: tuple[ParsedAppendixSection, ...],
    pronunciation: tuple[ParsedAppendixSection, ...],
) -> list[KnowledgePoint]:
    points: list[KnowledgePoint] = []
    for section in notes:
        node = nodes_by_title.get(section.unit_title or "")
        if node is None:
            continue
        slug = (section.unit_title or "general").casefold().replace(" ", "-")
        points.append(
            KnowledgePoint(
                source_id=source_id,
                curriculum_node_id=node.id,
                canonical_key=f"notes-on-text.{slug}.{str(source_id)[:8]}",
                type="text_note",
                title=f"{section.unit_title} Notes on the Text",
                summary="教材注释：重点句式、语法用法与地道英语文化知识。",
                source_page=f"P.{section.printed_pages}",
                difficulty=0.3,
                status="draft",
                content={
                    "origin": "notes_on_text_parser",
                    "role": "unit_reference",
                    "extracted_text": section.text,
                    "evidence_pdf_pages": list(section.pdf_pages),
                    "requires_review": True,
                },
            )
        )

    for section in pronunciation:
        unit_title = section.unit_title or "Starter Unit 1"
        node = nodes_by_title.get(unit_title)
        if node is None:
            continue
        slug = (section.unit_title or "foundations").casefold().replace(" ", "-")
        points.append(
            KnowledgePoint(
                source_id=source_id,
                curriculum_node_id=node.id,
                canonical_key=f"pronunciation.{slug}.{str(source_id)[:8]}",
                type="pronunciation",
                title=(
                    f"{section.unit_title} Pronunciation" if section.unit_title else "英语语音基础"
                ),
                summary=(
                    "本册核心语音训练：音素、拼读规则、重音、连读及英美音差异。"
                    if section.unit_title is None
                    else "本单元核心拼读规则、音素辨析与朗读训练。"
                ),
                source_page=f"P.{section.printed_pages}",
                difficulty=0.35,
                status="draft",
                content={
                    "origin": "pronunciation_appendix_parser",
                    "role": "core_pronunciation",
                    "priority": "core",
                    "extracted_text": section.text,
                    "evidence_pdf_pages": list(section.pdf_pages),
                    "requires_review": True,
                },
            )
        )

    for topic in GRADE7_UPPER_GRAMMAR_TOPICS:
        primary = str(topic["primary"])
        node = nodes_by_title.get(primary)
        if node is None:
            continue
        points.append(
            KnowledgePoint(
                source_id=source_id,
                curriculum_node_id=node.id,
                canonical_key=f"grammar-reference.{topic['key']}.{str(source_id)[:8]}",
                type="grammar",
                title=str(topic["title"]),
                summary=str(topic["summary"]),
                source_page=f"P.{topic['page']}",
                difficulty=0.35,
                status="draft",
                content={
                    "origin": "grammar_appendix_mapping",
                    "role": "grammar_reference",
                    "primary_unit": primary,
                    "related_units": topic["related"],
                    "mapping_basis": "教材单元目标语言、Grammar Focus 与附录例句",
                    "requires_review": False,
                },
            )
        )
    return points


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
    manifest, parser_profile = profile_for_source(source.filename)
    parsed = await asyncio.to_thread(_parse_pdf, path)
    reader = PdfReader(path)
    vocabulary_entries = await asyncio.to_thread(lambda: _parse_unit_vocabulary(reader))
    is_grade7_upper = "七年级上册" in source.filename
    notes = (
        await asyncio.to_thread(lambda: _parse_notes_on_the_text(reader)) if is_grade7_upper else ()
    )
    pronunciation = (
        await asyncio.to_thread(lambda: _parse_pronunciation(reader)) if is_grade7_upper else ()
    )
    page_texts = [page.extract_text() or "" for page in reader.pages]
    used_toc_fallback = False
    if not parsed.units and "七年级下册" in source.filename:
        parsed = ParsedTextbook(
            page_count=parsed.page_count,
            units=PEP_GRADE7_LOWER_UNITS,
            text_char_count=parsed.text_char_count,
        )
        used_toc_fallback = True
    if not parsed.units and manifest and manifest.unit_titles:
        parsed = ParsedTextbook(
            page_count=parsed.page_count,
            units=tuple(
                ParsedUnit(title=title, subtitle="", page_number=index)
                for index, title in enumerate(manifest.unit_titles, start=1)
            ),
            text_char_count=parsed.text_char_count,
        )
        used_toc_fallback = True

    await db.execute(delete(KnowledgePoint).where(KnowledgePoint.source_id == source.id))
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
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
    if is_grade7_upper:
        knowledge_points.extend(
            _appendix_knowledge(source.id, nodes_by_title, notes, pronunciation)
        )
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
                summary=f"{entry.unit_title} 单元词表第 {entry.unit_order} 个词条。",
                source_page="Words and Expressions",
                difficulty=0.2,
                status="draft",
                content={
                    "origin": "unit_wordlist_sequence_parser",
                    "role": "unit_wordlist",
                    "lemma": entry.canonical_expression,
                    "unit_order": entry.unit_order,
                    "raw_line": entry.raw_line,
                    "confidence": entry.confidence,
                    "warnings": list(entry.warnings),
                    "requires_review": entry.confidence < 0.75 or bool(entry.warnings),
                    "dictionary_status": "pending",
                },
            )
        )
    for point in knowledge_points:
        db.add(point)
    chunk_count = await build_chunks(db, source, page_texts, nodes, model_router)
    rag_metadata = source.metadata_ or {}
    parser_report = build_parser_report(
        profile=parser_profile,
        unit_count=len(nodes),
        vocabulary_entries=vocabulary_entries,
        page_texts=page_texts,
    )

    source.page_count = parsed.page_count
    source.unit_count = len(nodes)
    source.knowledge_count = len(knowledge_points)
    source.status = (
        "index_failed"
        if rag_metadata.get("rag_index_status") == "index_failed"
        else "partial_indexed"
        if rag_metadata.get("rag_index_status") == "partial_indexed"
        else "review_required"
    )
    source.metadata_ = {
        **rag_metadata,
        "stage": "validated",
        "text_char_count": parsed.text_char_count,
        "book_manifest_id": manifest.id if manifest else None,
        "parser_profile": parser_profile.id if parser_profile else None,
        "parser": "pypdf+manifest-profile-v1",
        "vocabulary_parser": "unit-sequence-with-evidence-v1",
        "dictionary_enrichment": "free_dictionary_api+mymemory",
        "vocabulary_entry_count": len(vocabulary_entries),
        "low_confidence_vocabulary_count": parser_report.low_confidence_entries,
        "notes_section_count": len(notes),
        "pronunciation_section_count": len(pronunciation),
        "grammar_reference_count": len(GRADE7_UPPER_GRAMMAR_TOPICS) if is_grade7_upper else 0,
        "rag_chunk_count": chunk_count,
        "toc_fallback": used_toc_fallback,
        "parser_report": parser_report.to_dict(),
        "warning": "; ".join(parser_report.warnings) if parser_report.warnings else None,
    }
    await db.flush()
    return parsed


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    return result.scalar_one_or_none()
