import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.error_pattern import ErrorPattern
from src.models.learner import Learner
from src.models.session import LearningSession
from src.models.vocabulary import ReviewSchedule, VocabularyItem

router = APIRouter(prefix="/api/learners/{learner_id}/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    today_reviews: int = 0
    streak_days: int = 0
    accuracy: int = 0
    total_vocab: int = 0


class DashboardReviewItem(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    definition: str | None = None
    example: str | None = None
    confidence: float


class DashboardErrorPattern(BaseModel):
    id: uuid.UUID
    name: str
    count: int
    example: str | None = None
    severity: str | None = None


class DashboardGoal(BaseModel):
    label: str
    completed: int
    total: int


class DashboardResponse(BaseModel):
    stats: DashboardStats
    review_items: list[DashboardReviewItem] = Field(default_factory=list)
    error_patterns: list[DashboardErrorPattern] = Field(default_factory=list)
    today_goal: DashboardGoal
    weekly_goal: DashboardGoal


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
            for key in ("definition", "meaning", "content", "text", "en"):
                text = first.get(key)
                if isinstance(text, str) and text:
                    return text
    if isinstance(value, dict):
        for key in ("definition", "meaning", "content", "text", "en"):
            text = value.get(key)
            if isinstance(text, str) and text:
                return text
    return None


def _streak_days(sessions: list[LearningSession]) -> int:
    completed_days = {
        session.completed_at.astimezone(timezone.utc).date()
        for session in sessions
        if session.completed_at is not None
    }
    if not completed_days:
        return 0

    today = datetime.now(timezone.utc).date()
    streak = 0
    cursor = today
    while cursor in completed_days:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return streak


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    await _ensure_learner_exists(db, learner_id)
    now = datetime.now(timezone.utc)

    total_vocab_result = await db.execute(
        select(func.count()).select_from(VocabularyItem).where(VocabularyItem.learner_id == learner_id)
    )
    total_vocab = int(total_vocab_result.scalar_one() or 0)

    due_count_result = await db.execute(
        select(func.count())
        .select_from(VocabularyItem)
        .where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItem.status != "mastered",
            VocabularyItem.next_review_at <= now,
        )
    )
    today_reviews = int(due_count_result.scalar_one() or 0)

    review_result = await db.execute(
        select(ReviewSchedule)
        .where(
            ReviewSchedule.learner_id == learner_id,
            ReviewSchedule.completed_at.is_not(None),
        )
        .order_by(ReviewSchedule.completed_at.desc())
        .limit(50)
    )
    recent_reviews = list(review_result.scalars().all())
    accuracy = 0
    if recent_reviews:
        correct = sum(1 for review in recent_reviews if review.result == "correct")
        accuracy = round(correct / len(recent_reviews) * 100)

    sessions_result = await db.execute(
        select(LearningSession)
        .where(
            LearningSession.learner_id == learner_id,
            LearningSession.status == "completed",
            LearningSession.completed_at.is_not(None),
        )
        .order_by(LearningSession.completed_at.desc())
        .limit(30)
    )
    sessions = list(sessions_result.scalars().all())
    streak_days = _streak_days(sessions)

    review_items_result = await db.execute(
        select(VocabularyItem)
        .where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItem.status != "mastered",
            VocabularyItem.next_review_at <= now,
        )
        .order_by(VocabularyItem.next_review_at.asc())
        .limit(5)
    )
    review_items = [
        DashboardReviewItem(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            definition=_first_text(item.meanings),
            example=_first_text(item.examples),
            confidence=item.confidence,
        )
        for item in review_items_result.scalars().all()
    ]

    error_result = await db.execute(
        select(ErrorPattern)
        .where(ErrorPattern.learner_id == learner_id)
        .order_by(ErrorPattern.frequency.desc(), ErrorPattern.updated_at.desc())
        .limit(5)
    )
    error_patterns = [
        DashboardErrorPattern(
            id=pattern.id,
            name=pattern.pattern,
            count=pattern.frequency,
            example=pattern.description,
            severity=pattern.severity,
        )
        for pattern in error_result.scalars().all()
    ]

    today = now.date()
    today_completed = sum(
        1 for session in sessions if session.completed_at and session.completed_at.date() == today
    )
    weekly_completed = min(len(sessions), 5)

    return DashboardResponse(
        stats=DashboardStats(
            today_reviews=today_reviews,
            streak_days=streak_days,
            accuracy=accuracy,
            total_vocab=total_vocab,
        ),
        review_items=review_items,
        error_patterns=error_patterns,
        today_goal=DashboardGoal(label="今日课程", completed=today_completed, total=1),
        weekly_goal=DashboardGoal(label="本周练习", completed=weekly_completed, total=5),
    )
