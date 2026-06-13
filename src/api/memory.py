import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.error_pattern import ErrorPattern
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage
from src.models.session import LearningSession
from src.models.vocabulary import VocabularyItem

router = APIRouter(prefix="/api/learners/{learner_id}/memory", tags=["memory"])


class MemoryLearner(BaseModel):
    id: uuid.UUID
    nickname: str
    email: str | None = None


class MemoryStats(BaseModel):
    conversation_count: int = 0
    message_count: int = 0
    total_vocab: int = 0
    due_reviews: int = 0
    mastered_vocab: int = 0


class MemoryErrorPattern(BaseModel):
    id: uuid.UUID
    name: str
    count: int
    severity: str | None = None


class MemorySession(BaseModel):
    id: uuid.UUID
    summary: str | None = None
    active_skill: str | None = None
    completed_at: datetime | None = None


class MemorySummaryResponse(BaseModel):
    learner: MemoryLearner
    stats: MemoryStats
    latest_thread_id: uuid.UUID | None = None
    latest_thread_title: str | None = None
    latest_thread_summary: str | None = None
    error_patterns: list[MemoryErrorPattern] = Field(default_factory=list)
    recent_sessions: list[MemorySession] = Field(default_factory=list)


@router.get("/summary", response_model=MemorySummaryResponse)
async def get_memory_summary(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MemorySummaryResponse:
    learner_result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = learner_result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    thread_result = await db.execute(
        select(AgentThread).where(AgentThread.learner_id == learner_id)
    )
    threads = list(thread_result.scalars().all())
    latest_thread = sorted(threads, key=_thread_activity_key, reverse=True)[0] if threads else None

    message_count_result = await db.execute(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.learner_id == learner_id)
    )
    total_vocab_result = await db.execute(
        select(func.count()).select_from(VocabularyItem).where(VocabularyItem.learner_id == learner_id)
    )
    mastered_vocab_result = await db.execute(
        select(func.count())
        .select_from(VocabularyItem)
        .where(VocabularyItem.learner_id == learner_id, VocabularyItem.status == "mastered")
    )
    due_reviews_result = await db.execute(
        select(func.count())
        .select_from(VocabularyItem)
        .where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItem.status != "mastered",
            VocabularyItem.next_review_at <= datetime.now(timezone.utc),
        )
    )

    error_result = await db.execute(
        select(ErrorPattern)
        .where(ErrorPattern.learner_id == learner_id)
        .order_by(ErrorPattern.frequency.desc(), ErrorPattern.updated_at.desc())
        .limit(5)
    )
    session_result = await db.execute(
        select(LearningSession)
        .where(LearningSession.learner_id == learner_id)
        .order_by(LearningSession.completed_at.desc(), LearningSession.created_at.desc())
        .limit(3)
    )

    metadata = latest_thread.metadata_ if latest_thread and latest_thread.metadata_ else {}
    return MemorySummaryResponse(
        learner=MemoryLearner(id=learner.id, nickname=learner.nickname, email=learner.email),
        stats=MemoryStats(
            conversation_count=len(threads),
            message_count=int(message_count_result.scalar_one() or 0),
            total_vocab=int(total_vocab_result.scalar_one() or 0),
            due_reviews=int(due_reviews_result.scalar_one() or 0),
            mastered_vocab=int(mastered_vocab_result.scalar_one() or 0),
        ),
        latest_thread_id=latest_thread.id if latest_thread else None,
        latest_thread_title=_metadata_text(metadata, "title"),
        latest_thread_summary=_metadata_text(metadata, "summary"),
        error_patterns=[
            MemoryErrorPattern(
                id=pattern.id,
                name=pattern.pattern,
                count=pattern.frequency,
                severity=pattern.severity,
            )
            for pattern in error_result.scalars().all()
        ],
        recent_sessions=[
            MemorySession(
                id=session.id,
                summary=session.summary,
                active_skill=session.active_skill,
                completed_at=session.completed_at,
            )
            for session in session_result.scalars().all()
        ],
    )


def _metadata_text(metadata: dict, key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _thread_activity_key(thread: AgentThread) -> datetime:
    metadata = thread.metadata_ or {}
    last_message_at = metadata.get("last_message_at")
    if isinstance(last_message_at, str):
        try:
            return datetime.fromisoformat(last_message_at)
        except ValueError:
            pass
    return thread.updated_at or thread.created_at or datetime.min.replace(tzinfo=timezone.utc)
