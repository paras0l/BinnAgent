import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.learner import Learner
from src.models.reading import ReadingMaterialHistory

router = APIRouter(tags=["reading-workshop"])

ReadingLevel = Literal["junior", "cet4", "cet6", "general"]
ReadingGoal = Literal["intensive", "extensive", "mixed"]


class ReadingTitleSuggestionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


class ReadingTitleSuggestionResponse(BaseModel):
    is_complete: bool
    suggested_title: str | None = None
    reason: str
    word_count: int
    sentence_count: int


class ReadingMaterialHistoryRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=1, max_length=12000)
    level: ReadingLevel = "general"
    goal: ReadingGoal = "mixed"


class ReadingMaterialHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    title: str | None = None
    text: str
    level: ReadingLevel
    goal: ReadingGoal
    word_count: int
    sentence_count: int
    source: str
    created_at: datetime
    updated_at: datetime


_SENTENCE_PATTERN = re.compile(r"[^.!?]+(?:[.!?]+[\"')\]]*)?|[^.!?]+$")
_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?")
_STOP_WORDS = {
    "about",
    "after",
    "also",
    "because",
    "between",
    "could",
    "every",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "should",
    "some",
    "such",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}


@router.post("/api/reading-workshop/title-suggestion", response_model=ReadingTitleSuggestionResponse)
async def suggest_reading_title(
    body: ReadingTitleSuggestionRequest,
) -> ReadingTitleSuggestionResponse:
    raw_text = body.text.strip()
    text = _normalize_text(raw_text)
    sentences = _split_sentences(text)
    words = _words(text)
    is_complete, reason = _assess_complete_material(text, sentences, words)

    return ReadingTitleSuggestionResponse(
        is_complete=is_complete,
        suggested_title=_suggest_title(raw_text, sentences, words) if is_complete else None,
        reason=reason,
        word_count=len(words),
        sentence_count=len(sentences),
    )


@router.get(
    "/api/learners/{learner_id}/reading-workshop/materials",
    response_model=list[ReadingMaterialHistoryResponse],
)
async def list_reading_materials(
    learner_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> list[ReadingMaterialHistory]:
    await _ensure_learner_exists(db, learner_id)
    result = await db.execute(
        select(ReadingMaterialHistory)
        .where(ReadingMaterialHistory.learner_id == learner_id)
        .order_by(ReadingMaterialHistory.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post(
    "/api/learners/{learner_id}/reading-workshop/materials",
    response_model=ReadingMaterialHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_reading_material(
    learner_id: uuid.UUID,
    body: ReadingMaterialHistoryRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReadingMaterialHistory:
    await _ensure_learner_exists(db, learner_id)
    stored_text = body.text.strip()
    normalized_text = _normalize_text(stored_text)
    words = _words(normalized_text)
    sentences = _split_sentences(normalized_text)
    text_hash = _text_hash(normalized_text)
    normalized_title = body.title.strip() if body.title and body.title.strip() else None

    result = await db.execute(
        select(ReadingMaterialHistory).where(
            ReadingMaterialHistory.learner_id == learner_id,
            ReadingMaterialHistory.text_hash == text_hash,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        material = ReadingMaterialHistory(
            learner_id=learner_id,
            text=stored_text,
            text_hash=text_hash,
            source="reading_workshop",
        )
        db.add(material)

    material.title = normalized_title
    material.text = stored_text
    material.level = body.level
    material.goal = body.goal
    material.word_count = len(words)
    material.sentence_count = len(sentences)
    material.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(material)
    return material


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in _SENTENCE_PATTERN.finditer(text) if match.group(0).strip()]


def _words(text: str) -> list[str]:
    return _WORD_PATTERN.findall(text)


def _assess_complete_material(text: str, sentences: list[str], words: list[str]) -> tuple[bool, str]:
    if len(words) < 30:
        return False, "material_too_short"
    if len(sentences) < 2:
        return False, "needs_more_sentences"
    if not re.search(r'[.!?]["\')\]]*$', text):
        return False, "missing_terminal_punctuation"
    return True, "complete_enough_for_title"


def _suggest_title(text: str, sentences: list[str], words: list[str]) -> str:
    explicit_title = _explicit_title(text)
    if explicit_title:
        return explicit_title

    candidates = _keyword_candidates(words)
    if candidates:
        return _title_case(" ".join(candidates[:4]))

    first_sentence = sentences[0] if sentences else text
    first_words = _words(first_sentence)[:7]
    return _title_case(" ".join(first_words)) or "Reading Material"


def _explicit_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    first_line_words = _words(lines[0])
    if 2 <= len(first_line_words) <= 10 and not re.search(r"[.!?]$", lines[0]):
        return _title_case(" ".join(first_line_words))
    return None


def _keyword_candidates(words: list[str]) -> list[str]:
    counts: dict[str, tuple[int, int]] = {}
    for index, raw_word in enumerate(words):
        word = raw_word.lower()
        if len(word) < 4 or word in _STOP_WORDS:
            continue
        count, first_index = counts.get(word, (0, index))
        counts[word] = (count + 1, first_index)

    return [
        word
        for word, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1][0], item[1][1], item[0]),
        )
    ]


def _title_case(text: str) -> str:
    small_words = {"and", "as", "for", "in", "of", "on", "or", "the", "to", "with"}
    words = _words(text)
    if not words:
        return ""

    titled: list[str] = []
    for index, word in enumerate(words):
        lowered = word.lower()
        if 0 < index < len(words) - 1 and lowered in small_words:
            titled.append(lowered)
        else:
            titled.append(lowered.capitalize())
    return " ".join(titled)[:80]


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
