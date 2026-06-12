import uuid

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.vocabulary_store import VocabularyStore

router = APIRouter(prefix="/api/learners/{learner_id}/vocabulary", tags=["vocabulary"])


class AddWordRequest(BaseModel):
    word: str
    phonetic: str | None = None
    level: str | None = None
    meanings: list[str] | None = None


class ReviewWordRequest(BaseModel):
    word_id: str
    correct: bool
    response_time_ms: int | None = None


class WordResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    next_review_at: str | None = None


@router.post("/add", response_model=WordResponse)
async def add_word(
    learner_id: uuid.UUID,
    req: AddWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    store = VocabularyStore(db)
    item = await store.add_word(
        learner_id=learner_id,
        word=req.word,
        phonetic=req.phonetic,
        level=req.level,
        meanings=req.meanings,
    )
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
    store = VocabularyStore(db)
    item = await store.update_confidence(
        item_id=uuid.UUID(req.word_id),
        correct=req.correct,
        response_time_ms=req.response_time_ms,
    )
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
