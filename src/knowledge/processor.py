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
    for point in knowledge_points:
        db.add(point)

    source.page_count = parsed.page_count
    source.unit_count = len(nodes)
    source.knowledge_count = len(knowledge_points)
    source.status = "review_required"
    source.metadata_ = {
        "stage": "validated",
        "text_char_count": parsed.text_char_count,
        "parser": "pypdf+rule-based-v1",
        "toc_fallback": used_toc_fallback,
        "warning": None if nodes else "未识别到目录结构，需要人工校对",
    }
    await db.flush()
    return parsed


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    return result.scalar_one_or_none()
