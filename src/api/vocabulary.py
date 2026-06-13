import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.vocabulary_store import VocabularyStore
from src.models.learner import Learner
from src.models.vocabulary import VocabularyItem

router = APIRouter(prefix="/api/learners/{learner_id}/vocabulary", tags=["vocabulary"])


class AddWordRequest(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    phonetic: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=20)
    meanings: list[str] | None = None

    @field_validator("word")
    @classmethod
    def word_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Word must not be blank")
        return stripped


class ReviewWordRequest(BaseModel):
    word_id: uuid.UUID
    correct: bool
    response_time_ms: int | None = Field(default=None, ge=0)


class WordResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    next_review_at: str | None = None


class VocabularyListItemResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    review_count: int
    meaning: str | None = None
    last_reviewed_at: str | None = None
    next_review_at: str | None = None


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("definition", "meaning", "content", "text", "zh", "en"):
                text = first.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    if isinstance(value, dict):
        for key in ("definition", "meaning", "content", "text", "zh", "en"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else str(value) if value else None


@router.get("", response_model=list[VocabularyListItemResponse])
async def list_vocabulary(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[VocabularyListItemResponse]:
    await _ensure_learner_exists(db, learner_id)

    result = await db.execute(
        select(VocabularyItem)
        .where(VocabularyItem.learner_id == learner_id)
        .order_by(
            VocabularyItem.last_reviewed_at.desc().nullslast(),
            VocabularyItem.updated_at.desc(),
            VocabularyItem.created_at.desc(),
        )
    )
    return [
        VocabularyListItemResponse(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            status=item.status,
            confidence=item.confidence,
            review_count=item.review_count,
            meaning=_first_text(item.meanings),
            last_reviewed_at=_iso(item.last_reviewed_at),
            next_review_at=_iso(item.next_review_at),
        )
        for item in result.scalars().all()
    ]


@router.post("/add", response_model=WordResponse)
async def add_word(
    learner_id: uuid.UUID,
    req: AddWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        item = await store.add_word(
            learner_id=learner_id,
            word=req.word,
            phonetic=req.phonetic,
            level=req.level,
            meanings=req.meanings,
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid vocabulary word")
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at.isoformat()
        if hasattr(item.next_review_at, "isoformat")
        else str(item.next_review_at)
        if item.next_review_at
        else None,
    )


@router.get("/due", response_model=list[WordResponse])
async def get_due_reviews(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    items = await store.get_due_reviews(learner_id)
    return [
        WordResponse(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            status=item.status,
            confidence=item.confidence,
            next_review_at=item.next_review_at.isoformat()
            if hasattr(item.next_review_at, "isoformat")
            else str(item.next_review_at)
            if item.next_review_at
            else None,
        )
        for item in items
    ]


@router.post("/review", response_model=WordResponse)
async def review_word(
    learner_id: uuid.UUID,
    req: ReviewWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        item = await store.update_confidence(
            learner_id=learner_id,
            item_id=req.word_id,
            correct=req.correct,
            response_time_ms=req.response_time_ms,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at.isoformat()
        if hasattr(item.next_review_at, "isoformat")
        else str(item.next_review_at)
        if item.next_review_at
        else None,
    )


@router.delete("/{word_id}", status_code=204)
async def delete_word(
    learner_id: uuid.UUID,
    word_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _ensure_learner_exists(db, learner_id)

    store = VocabularyStore(db)
    try:
        await store.delete_word(learner_id=learner_id, item_id=word_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
