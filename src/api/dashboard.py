import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, require_learner_access
from src.models.error_pattern import ErrorPattern
from src.models.knowledge import ExerciseAttempt, LearnerKnowledgeState
from src.models.learner import Learner
from src.models.learning_progress import LearningProgressItem
from src.models.runtime import ConversationMessage
from src.models.session import LearningSession
from src.models.vocabulary import ReviewSchedule, VocabularyItem, VocabularyMasteryVector

router = APIRouter(prefix="/api/learners/{learner_id}/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    today_reviews: int = 0
    today_completed_reviews: int = 0
    today_ai_conversations: int = 0
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


class DashboardDailyActivity(BaseModel):
    date: str
    count: int


class DashboardProfileAbility(BaseModel):
    label: str
    value: int
    evidence_count: int = 0


class DashboardProfileMasteryBucket(BaseModel):
    label: str
    value: int


class DashboardProfileTrendPoint(BaseModel):
    date: str
    accuracy: int
    due_reviews: int


class DashboardProfileData(BaseModel):
    ability_scores: list[DashboardProfileAbility] = Field(default_factory=list)
    mastery_buckets: list[DashboardProfileMasteryBucket] = Field(default_factory=list)
    trend: list[DashboardProfileTrendPoint] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    stats: DashboardStats
    review_items: list[DashboardReviewItem] = Field(default_factory=list)
    error_patterns: list[DashboardErrorPattern] = Field(default_factory=list)
    today_goal: DashboardGoal
    weekly_goal: DashboardGoal
    daily_activity: list[DashboardDailyActivity] = Field(default_factory=list)
    profile: DashboardProfileData = Field(default_factory=DashboardProfileData)


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in (
                "definition_zh",
                "sentence",
                "definition",
                "meaning",
                "content",
                "text",
                "definition_en",
                "en",
            ):
                text = first.get(key)
                if isinstance(text, str) and text:
                    return text
    if isinstance(value, dict):
        for key in (
            "definition_zh",
            "sentence",
            "definition",
            "meaning",
            "content",
            "text",
            "definition_en",
            "en",
        ):
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


def _score_from_attempts(attempts: list[ExerciseAttempt]) -> int | None:
    gradable_attempts = [
        attempt for attempt in attempts if attempt.result in {"correct", "incorrect"}
    ]
    if not gradable_attempts:
        return None
    correct_count = sum(1 for attempt in gradable_attempts if attempt.correct)
    return round(correct_count / len(gradable_attempts) * 100)


def _reading_score_from_attempts(attempts: list[ExerciseAttempt]) -> tuple[int | None, int]:
    scores: list[float] = []
    for attempt in attempts:
        metadata = attempt.metadata_ or {}
        if metadata.get("source") == "reading_workshop_completion":
            value = metadata.get("comprehension_score")
            if isinstance(value, (int, float)):
                scores.append(max(0.0, min(100.0, float(value))))
            continue
        if attempt.result in {"correct", "incorrect"}:
            scores.append(100.0 if attempt.correct else 0.0)
    if not scores:
        return None, 0
    return _clamp_percent(sum(scores) / len(scores)), len(scores)


def _progress_score(items: list[LearningProgressItem]) -> int | None:
    if not items:
        return None
    learned = sum(1 for item in items if item.status == "learned")
    opened = sum(1 for item in items if item.opened_count > 0 or item.status in {"opened", "learned"})
    return round(((learned * 1.0) + max(0, opened - learned) * 0.45) / len(items) * 100)


def _average(values: list[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def _clamp_percent(value: float) -> int:
    return max(0, min(100, round(value)))


def _skill_key(value: str | None) -> str:
    normalized = (value or "").lower()
    if "grammar" in normalized or "语法" in normalized:
        return "grammar"
    if "read" in normalized or "阅读" in normalized:
        return "reading"
    if "writ" in normalized or "写作" in normalized or "essay" in normalized:
        return "writing"
    if "pronunciation" in normalized or "phonetic" in normalized or "发音" in normalized:
        return "pronunciation"
    if "listen" in normalized or "听力" in normalized:
        return "listening"
    if "vocab" in normalized or "word" in normalized or "词" in normalized:
        return "vocabulary"
    return normalized or "general"


def _combine_scores(scores: list[tuple[float | None, int]]) -> tuple[int | None, int]:
    weighted_total = 0.0
    evidence_total = 0
    for score, evidence_count in scores:
        if score is None or evidence_count <= 0:
            continue
        weighted_total += score * evidence_count
        evidence_total += evidence_count
    if evidence_total == 0:
        return None, 0
    return _clamp_percent(weighted_total / evidence_total), evidence_total


def _profile_ability_scores(
    vocab_items: list[VocabularyItem],
    mastery_vectors: list[VocabularyMasteryVector],
    progress_items: list[LearningProgressItem],
    exercise_attempts: list[ExerciseAttempt],
) -> list[DashboardProfileAbility]:
    attempts_by_skill: dict[str, list[ExerciseAttempt]] = {}
    for attempt in exercise_attempts:
        attempts_by_skill.setdefault(_skill_key(attempt.target_type), []).append(attempt)

    progress_by_skill: dict[str, list[LearningProgressItem]] = {}
    for item in progress_items:
        progress_by_skill.setdefault(_skill_key(item.skill), []).append(item)

    vocab_confidence = _average([item.confidence * 100 for item in vocab_items])
    vocab_vector_scores: list[float] = []
    for vector in mastery_vectors:
        vector_score = _average(
            [
                vector.recognition,
                vector.recall,
                vector.spelling,
                vector.context_use,
                vector.production,
            ]
        )
        if vector_score is not None:
            vocab_vector_scores.append(vector_score * 100)
    vocab_vector = _average(vocab_vector_scores)
    listening_vector = _average([vector.listening * 100 for vector in mastery_vectors])
    reading_score, reading_evidence_count = _reading_score_from_attempts(
        attempts_by_skill.get("reading", [])
    )

    skill_sources = {
        "词汇": [
            (vocab_confidence, len(vocab_items)),
            (vocab_vector, len(mastery_vectors)),
            (
                _score_from_attempts(attempts_by_skill.get("vocabulary", [])),
                len(attempts_by_skill.get("vocabulary", [])),
            ),
        ],
        "语法": [
            (_progress_score(progress_by_skill.get("grammar", [])), len(progress_by_skill.get("grammar", []))),
            (
                _score_from_attempts(attempts_by_skill.get("grammar", [])),
                len(attempts_by_skill.get("grammar", [])),
            ),
        ],
        "阅读": [
            (reading_score, reading_evidence_count),
        ],
        "写作": [
            (_score_from_attempts(attempts_by_skill.get("writing", [])), len(attempts_by_skill.get("writing", []))),
        ],
        "发音": [
            (_progress_score(progress_by_skill.get("pronunciation", [])), len(progress_by_skill.get("pronunciation", []))),
            (_score_from_attempts(attempts_by_skill.get("pronunciation", [])), len(attempts_by_skill.get("pronunciation", []))),
        ],
        "听力": [
            (listening_vector, len(mastery_vectors)),
            (_score_from_attempts(attempts_by_skill.get("listening", [])), len(attempts_by_skill.get("listening", []))),
        ],
    }

    ability_scores: list[DashboardProfileAbility] = []
    for label, sources in skill_sources.items():
        score, evidence_count = _combine_scores(sources)
        if score is not None:
            ability_scores.append(
                DashboardProfileAbility(label=label, value=score, evidence_count=evidence_count)
            )
    return ability_scores


def _mastery_buckets(
    vocab_items: list[VocabularyItem],
    knowledge_states: list[LearnerKnowledgeState],
    mastery_vectors: list[VocabularyMasteryVector],
) -> list[DashboardProfileMasteryBucket]:
    scores = [item.confidence for item in vocab_items]
    scores.extend(state.mastery_score for state in knowledge_states)
    for vector in mastery_vectors:
        vector_score = _average(
            [
                vector.recognition,
                vector.recall,
                vector.spelling,
                vector.listening,
                vector.context_use,
                vector.production,
            ]
        )
        if vector_score is not None:
            scores.append(vector_score)

    buckets = {"新学": 0, "学习中": 0, "熟悉": 0, "掌握": 0}
    for score in scores:
        if score <= 0:
            buckets["新学"] += 1
        elif score < 0.5:
            buckets["学习中"] += 1
        elif score < 0.8:
            buckets["熟悉"] += 1
        else:
            buckets["掌握"] += 1
    return [DashboardProfileMasteryBucket(label=label, value=value) for label, value in buckets.items()]


def _profile_trend(
    days: list[date],
    review_schedules: list[ReviewSchedule],
    exercise_attempts: list[ExerciseAttempt],
    due_review_counts: dict[date, int],
) -> list[DashboardProfileTrendPoint]:
    points: list[DashboardProfileTrendPoint] = []
    for day in days:
        correct = 0
        total = 0
        for review in review_schedules:
            if review.completed_at and review.completed_at.astimezone(timezone.utc).date() == day:
                total += 1
                if review.result == "correct":
                    correct += 1
        for attempt in exercise_attempts:
            if attempt.created_at and attempt.created_at.astimezone(timezone.utc).date() == day:
                if attempt.result not in {"correct", "incorrect"}:
                    continue
                total += 1
                if attempt.correct:
                    correct += 1
        points.append(
            DashboardProfileTrendPoint(
                date=day.isoformat(),
                accuracy=round(correct / total * 100) if total else 0,
                due_reviews=int(due_review_counts.get(day, 0)),
            )
        )
    return points


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    learner_id: uuid.UUID,
    _: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    now = datetime.now(timezone.utc)
    today = now.date()

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
    today_completed_reviews = sum(
        1
        for review in recent_reviews
        if review.completed_at is not None
        and review.completed_at.astimezone(timezone.utc).date() == today
    )

    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)
    today_ai_conversations_result = await db.execute(
        select(func.count())
        .select_from(ConversationMessage)
        .where(
            ConversationMessage.learner_id == learner_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.created_at >= today_start,
            ConversationMessage.created_at < tomorrow_start,
        )
    )
    today_ai_conversations = int(today_ai_conversations_result.scalar_one() or 0)

    sessions_result = await db.execute(
        select(LearningSession)
        .where(
            LearningSession.learner_id == learner_id,
            LearningSession.status == "completed",
            LearningSession.completed_at.is_not(None),
        )
        .order_by(LearningSession.completed_at.desc())
        .limit(180)
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

    today_completed = sum(
        1 for session in sessions if session.completed_at and session.completed_at.date() == today
    )
    weekly_completed = min(len(sessions), 5)
    session_counts = Counter(
        session.completed_at.astimezone(timezone.utc).date()
        for session in sessions
        if session.completed_at is not None
    )
    daily_activity = [
        DashboardDailyActivity(
            date=(today - timedelta(days=offset)).isoformat(),
            count=session_counts[today - timedelta(days=offset)],
        )
        for offset in range(13, -1, -1)
    ]
    trend_days = [today - timedelta(days=offset) for offset in range(13, -1, -1)]

    vocab_items_result = await db.execute(
        select(VocabularyItem).where(VocabularyItem.learner_id == learner_id).limit(5000)
    )
    profile_vocab_items = list(vocab_items_result.scalars().all())

    knowledge_states_result = await db.execute(
        select(LearnerKnowledgeState).where(LearnerKnowledgeState.learner_id == learner_id).limit(5000)
    )
    knowledge_states = list(knowledge_states_result.scalars().all())

    mastery_vectors_result = await db.execute(
        select(VocabularyMasteryVector).where(VocabularyMasteryVector.learner_id == learner_id).limit(5000)
    )
    mastery_vectors = list(mastery_vectors_result.scalars().all())

    progress_items_result = await db.execute(
        select(LearningProgressItem).where(LearningProgressItem.learner_id == learner_id).limit(5000)
    )
    progress_items = list(progress_items_result.scalars().all())

    attempts_result = await db.execute(
        select(ExerciseAttempt)
        .where(ExerciseAttempt.learner_id == learner_id)
        .order_by(ExerciseAttempt.created_at.desc())
        .limit(500)
    )
    exercise_attempts = list(attempts_result.scalars().all())

    recent_review_history_result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.learner_id == learner_id,
            ReviewSchedule.completed_at.is_not(None),
            ReviewSchedule.completed_at >= datetime.combine(trend_days[0], datetime.min.time(), tzinfo=timezone.utc),
        )
    )
    recent_review_history = list(recent_review_history_result.scalars().all())

    due_schedule_result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.learner_id == learner_id,
            ReviewSchedule.scheduled_at >= datetime.combine(
                trend_days[0], datetime.min.time(), tzinfo=timezone.utc
            ),
        )
    )
    due_review_counts = Counter(
        review.scheduled_at.astimezone(timezone.utc).date()
        for review in due_schedule_result.scalars().all()
        if review.scheduled_at is not None
    )

    return DashboardResponse(
        stats=DashboardStats(
            today_reviews=today_reviews,
            today_completed_reviews=today_completed_reviews,
            today_ai_conversations=today_ai_conversations,
            streak_days=streak_days,
            accuracy=accuracy,
            total_vocab=total_vocab,
        ),
        review_items=review_items,
        error_patterns=error_patterns,
        today_goal=DashboardGoal(label="今日课程", completed=today_completed, total=1),
        weekly_goal=DashboardGoal(label="本周练习", completed=weekly_completed, total=5),
        daily_activity=daily_activity,
        profile=DashboardProfileData(
            ability_scores=_profile_ability_scores(
                profile_vocab_items,
                mastery_vectors,
                progress_items,
                exercise_attempts,
            ),
            mastery_buckets=_mastery_buckets(profile_vocab_items, knowledge_states, mastery_vectors),
            trend=_profile_trend(
                trend_days,
                recent_review_history,
                [
                    attempt
                    for attempt in exercise_attempts
                    if attempt.created_at
                    and attempt.created_at.astimezone(timezone.utc).date() >= trend_days[0]
                ],
                due_review_counts,
            ),
        ),
    )
