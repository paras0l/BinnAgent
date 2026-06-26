import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.curator import MemoryCurator
from src.memory.explainer import MemoryExplainer
from src.memory.retriever import MemoryRetriever
from src.memory.writer import MemoryWriter
from src.models.error_pattern import ErrorPattern
from src.models.learner import Learner
from src.models.learning_progress import LearningProgressItem
from src.models.memory import (
    LearnerMemorySettings,
    LearningMemoryEvent,
    MemoryContextLog,
    MemoryOperation,
    WritingPhraseMastery,
)
from src.models.runtime import AgentThread, ConversationMessage
from src.models.session import LearningSession, LearningTask
from src.models.vocabulary import VocabularyItem
from src.models.writing_phrase import WritingPhrase

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


class MemorySkillProgress(BaseModel):
    grammar_learned: int = 0
    grammar_favorites: int = 0
    pronunciation_learned: int = 0
    pronunciation_opened: int = 0


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


class MemoryRecentEvent(BaseModel):
    id: uuid.UUID
    event_type: str
    skill: str
    source_type: str
    source_id: str | None = None
    confidence: float
    occurred_at: datetime
    summary: str


class MemorySummaryResponse(BaseModel):
    learner: MemoryLearner
    stats: MemoryStats
    latest_thread_id: uuid.UUID | None = None
    latest_thread_title: str | None = None
    latest_thread_summary: str | None = None
    error_patterns: list[MemoryErrorPattern] = Field(default_factory=list)
    recent_sessions: list[MemorySession] = Field(default_factory=list)
    recent_events: list[MemoryRecentEvent] = Field(default_factory=list)
    active_weaknesses: list[str] = Field(default_factory=list)
    skill_progress: MemorySkillProgress = Field(default_factory=MemorySkillProgress)


class MemoryCard(BaseModel):
    id: str
    type: str
    title: str
    content: str
    skill: str
    confidence: float
    status: str | None = None
    evidence: list[str] = Field(default_factory=list)
    impact: str
    updated_at: datetime | None = None
    editable: bool = True


class MemoryCenterResponse(BaseModel):
    learner: MemoryLearner
    cards: list[MemoryCard] = Field(default_factory=list)
    recommendation_reason: str
    metrics: dict[str, int] = Field(default_factory=dict)
    settings: dict[str, bool] = Field(default_factory=dict)


class MemoryControlRequest(BaseModel):
    operation: str = Field(pattern="^(edit|delete|disable|correct|mark_improved)$")
    content: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=500)


class MemoryControlResponse(BaseModel):
    target_id: str
    operation: str
    status: str


class MemoryCurateResponse(BaseModel):
    event_count: int
    active_weaknesses: list[str]


class MemorySettingsRequest(BaseModel):
    emotion_rhythm_enabled: bool | None = None
    inferred_preferences_enabled: bool | None = None
    low_confidence_memory_enabled: bool | None = None


class MemorySettingsResponse(BaseModel):
    emotion_rhythm_enabled: bool = False
    inferred_preferences_enabled: bool = True
    low_confidence_memory_enabled: bool = False


class MemoryResetPlanResponse(BaseModel):
    reset_task_count: int
    reset_session_count: int


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
    grammar_learned_result = await db.execute(
        select(func.count())
        .select_from(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "grammar",
            LearningProgressItem.status == "learned",
        )
    )
    grammar_favorites_result = await db.execute(
        select(func.count())
        .select_from(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "grammar",
            LearningProgressItem.is_favorite.is_(True),
        )
    )
    pronunciation_learned_result = await db.execute(
        select(func.count())
        .select_from(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "pronunciation",
            LearningProgressItem.status == "learned",
        )
    )
    pronunciation_opened_result = await db.execute(
        select(func.count())
        .select_from(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "pronunciation",
            LearningProgressItem.opened_count > 0,
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
    recent_event_result = await db.execute(
        select(LearningMemoryEvent)
        .where(
            LearningMemoryEvent.learner_id == learner_id,
            LearningMemoryEvent.visibility != "deleted",
        )
        .order_by(LearningMemoryEvent.occurred_at.desc())
        .limit(5)
    )
    active_weakness_result = await db.execute(
        select(ErrorPattern.skill)
        .where(
            ErrorPattern.learner_id == learner_id,
            ErrorPattern.status.in_(["active", "improving"]),
        )
        .order_by(ErrorPattern.frequency.desc())
        .limit(6)
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
        recent_events=[
            MemoryRecentEvent(
                id=event.id,
                event_type=event.event_type,
                skill=event.skill,
                source_type=event.source_type,
                source_id=event.source_id,
                confidence=event.confidence,
                occurred_at=event.occurred_at,
                summary=_event_summary(event),
            )
            for event in recent_event_result.scalars().all()
        ],
        active_weaknesses=list(dict.fromkeys(active_weakness_result.scalars().all())),
        skill_progress=MemorySkillProgress(
            grammar_learned=int(grammar_learned_result.scalar_one() or 0),
            grammar_favorites=int(grammar_favorites_result.scalar_one() or 0),
            pronunciation_learned=int(pronunciation_learned_result.scalar_one() or 0),
            pronunciation_opened=int(pronunciation_opened_result.scalar_one() or 0),
        ),
    )


@router.get("/center", response_model=MemoryCenterResponse)
async def get_memory_center(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MemoryCenterResponse:
    learner = await _ensure_learner(db, learner_id)
    cards = await _memory_cards(db, learner_id)
    retrieved = await MemoryRetriever(db).retrieve_context(
        learner_id=learner_id,
        reason="memory_center",
        skill="general",
        limit=5,
    )
    return MemoryCenterResponse(
        learner=MemoryLearner(id=learner.id, nickname=learner.nickname, email=learner.email),
        cards=cards,
        recommendation_reason=MemoryExplainer().recommendation_reason(
            retrieved.loaded_items,
            "推荐原因：当前会优先使用最近练习、活跃弱点和到期复习来安排任务。",
        ),
        metrics=await _memory_metrics(db, learner_id),
        settings=_settings_dict(await _get_or_create_settings(db, learner_id)),
    )


@router.post("/curate", response_model=MemoryCurateResponse)
async def curate_memory(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MemoryCurateResponse:
    await _ensure_learner(db, learner_id)
    result = await MemoryCurator(db).curate_learner(learner_id)
    await db.flush()
    return MemoryCurateResponse(**result)


@router.patch("/items/{target_type}/{target_id}", response_model=MemoryControlResponse)
async def control_memory_item(
    learner_id: uuid.UUID,
    target_type: str,
    target_id: str,
    body: MemoryControlRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MemoryControlResponse:
    await _ensure_learner(db, learner_id)
    before, after, status = await _apply_memory_control(
        db,
        learner_id=learner_id,
        target_type=target_type,
        target_id=target_id,
        operation=body.operation,
        content=body.content,
    )
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type=body.operation,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        reason=body.reason,
    )
    await db.flush()
    return MemoryControlResponse(target_id=target_id, operation=body.operation, status=status)


@router.get("/settings", response_model=MemorySettingsResponse)
async def get_memory_settings(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MemorySettingsResponse:
    await _ensure_learner(db, learner_id)
    return MemorySettingsResponse(**_settings_dict(await _get_or_create_settings(db, learner_id)))


@router.patch("/settings", response_model=MemorySettingsResponse)
async def update_memory_settings(
    learner_id: uuid.UUID,
    body: MemorySettingsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MemorySettingsResponse:
    await _ensure_learner(db, learner_id)
    settings = await _get_or_create_settings(db, learner_id)
    before = _settings_dict(settings)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            setattr(settings, key, value)
    after = _settings_dict(settings)
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type="edit",
        target_type="memory_settings",
        target_id=str(settings.id),
        before={"skill": "general", **before},
        after={"skill": "general", **after},
        reason="Updated memory privacy settings",
    )
    await db.flush()
    return MemorySettingsResponse(**after)


@router.post("/reset-plan", response_model=MemoryResetPlanResponse)
async def reset_learning_plan(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResetPlanResponse:
    await _ensure_learner(db, learner_id)
    task_result = await db.execute(
        select(LearningTask).where(
            LearningTask.learner_id == learner_id,
            LearningTask.status.in_(["pending", "in_progress", "active"]),
        )
    )
    tasks = list(task_result.scalars().all())
    session_result = await db.execute(
        select(LearningSession).where(
            LearningSession.learner_id == learner_id,
            LearningSession.status.in_(["pending", "active", "in_progress"]),
        )
    )
    sessions = list(session_result.scalars().all())
    now = datetime.now(timezone.utc)
    for task in tasks:
        task.status = "reset"
        task.completed_at = now
    for session in sessions:
        session.status = "reset"
        session.completed_at = now
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type="reset_plan",
        target_type="learning_plan",
        target_id=str(learner_id),
        before={"skill": "general", "task_count": len(tasks), "session_count": len(sessions)},
        after={"skill": "general", "status": "reset"},
        reason="User reset learning plan",
    )
    await db.flush()
    return MemoryResetPlanResponse(reset_task_count=len(tasks), reset_session_count=len(sessions))


@router.get("/export")
async def export_memory(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    learner = await _ensure_learner(db, learner_id)
    cards = await _memory_cards(db, learner_id)
    event_result = await db.execute(
        select(LearningMemoryEvent)
        .where(LearningMemoryEvent.learner_id == learner_id)
        .order_by(LearningMemoryEvent.occurred_at.desc())
        .limit(500)
    )
    await MemoryWriter(db).record_user_control_event(
        learner_id=learner_id,
        operation_type="export",
        target_type="memory",
        target_id=str(learner_id),
        after={"skill": "general", "card_count": len(cards)},
    )
    return {
        "learner": {"id": str(learner.id), "nickname": learner.nickname, "email": learner.email},
        "cards": [card.model_dump(mode="json") for card in cards],
        "events": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "skill": event.skill,
                "subskill": event.subskill,
                "source_type": event.source_type,
                "source_id": event.source_id,
                "payload": event.payload or {},
                "confidence": event.confidence,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in event_result.scalars().all()
        ],
    }


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


async def _ensure_learner(db: AsyncSession, learner_id: uuid.UUID) -> Learner:
    learner_result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = learner_result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return learner


def _event_summary(event: LearningMemoryEvent) -> str:
    payload = event.payload or {}
    if event.event_type == "chat_learning_turn":
        return str(payload.get("summary") or "完成一次学习对话。")
    if event.event_type == "vocabulary_attempted":
        return f"{payload.get('word', '词汇')}：{payload.get('result', '练习完成')}"
    if event.event_type == "knowledge_exercise_answered":
        return f"教材练习：{'正确' if payload.get('correct') else '需要订正'}"
    if event.event_type == "writing_phrase_attempted":
        return f"写作句式练习：得分 {payload.get('score', 0)}"
    return event.event_type.replace("_", " ")


async def _memory_cards(db: AsyncSession, learner_id: uuid.UUID) -> list[MemoryCard]:
    cards: list[MemoryCard] = []
    error_result = await db.execute(
        select(ErrorPattern)
        .where(ErrorPattern.learner_id == learner_id, ErrorPattern.status != "deleted")
        .order_by(ErrorPattern.updated_at.desc())
        .limit(20)
    )
    for pattern in error_result.scalars().all():
        cards.append(
            MemoryCard(
                id=f"error_pattern:{pattern.id}",
                type="error_pattern",
                title=pattern.pattern,
                content=pattern.description or pattern.pattern,
                skill=pattern.skill,
                confidence=float(pattern.confidence or 0.5),
                status=pattern.status,
                evidence=[str(item) for item in (pattern.evidence_refs or [])[:5]]
                if isinstance(pattern.evidence_refs, list)
                else [],
                impact=f"影响 {pattern.recommended_drill or 'targeted_practice'} 推荐",
                updated_at=pattern.updated_at,
            )
        )

    phrase_result = await db.execute(
        select(WritingPhraseMastery, WritingPhrase)
        .join(WritingPhrase, WritingPhrase.id == WritingPhraseMastery.phrase_id)
        .where(WritingPhraseMastery.learner_id == learner_id)
        .order_by(WritingPhraseMastery.updated_at.desc())
        .limit(20)
    )
    for mastery, phrase in phrase_result.all():
        cards.append(
            MemoryCard(
                id=f"writing_phrase_mastery:{mastery.id}",
                type="writing_phrase_mastery",
                title="写作句式掌握",
                content=phrase.text,
                skill="writing",
                confidence=float(mastery.confidence or 0.5),
                status=mastery.status,
                evidence=[str(item) for item in (mastery.evidence_refs or [])[:5]],
                impact=f"影响 {mastery.recommended_drill or 'writing_phrase_practice'} 推荐",
                updated_at=mastery.updated_at,
            )
        )

    event_result = await db.execute(
        select(LearningMemoryEvent)
        .where(
            LearningMemoryEvent.learner_id == learner_id,
            LearningMemoryEvent.visibility != "deleted",
        )
        .order_by(LearningMemoryEvent.occurred_at.desc())
        .limit(20)
    )
    for event in event_result.scalars().all():
        cards.append(
            MemoryCard(
                id=f"learning_memory_event:{event.id}",
                type="learning_memory_event",
                title=event.event_type.replace("_", " "),
                content=_event_summary(event),
                skill=event.skill,
                confidence=float(event.confidence or 0.5),
                status=event.visibility,
                evidence=[f"{event.source_type}:{event.source_id}"] if event.source_id else [],
                impact="影响最近学习上下文和任务推荐",
                updated_at=event.updated_at,
                editable=True,
            )
        )
    cards.sort(key=lambda card: card.updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return cards[:40]


async def _memory_metrics(db: AsyncSession, learner_id: uuid.UUID) -> dict[str, int]:
    event_count = await db.execute(
        select(func.count()).select_from(LearningMemoryEvent).where(LearningMemoryEvent.learner_id == learner_id)
    )
    operation_count = await db.execute(
        select(func.count()).select_from(MemoryOperation).where(MemoryOperation.learner_id == learner_id)
    )
    retrieval_count = await db.execute(
        select(func.count()).select_from(MemoryContextLog).where(MemoryContextLog.learner_id == learner_id)
    )
    used_count = await db.execute(
        select(func.count()).select_from(MemoryContextLog).where(
            MemoryContextLog.learner_id == learner_id,
            func.jsonb_array_length(MemoryContextLog.loaded_items) > 0,
        )
    )
    deleted_count = await db.execute(
        select(func.count()).select_from(MemoryOperation).where(
            MemoryOperation.learner_id == learner_id,
            MemoryOperation.operation_type == "delete",
        )
    )
    stale_count = await db.execute(
        select(func.count()).select_from(LearningMemoryEvent).where(
            LearningMemoryEvent.learner_id == learner_id,
            LearningMemoryEvent.confidence < 0.4,
            LearningMemoryEvent.visibility != "deleted",
        )
    )
    write_count = int(event_count.scalar_one() or 0)
    retrieval_total = int(retrieval_count.scalar_one() or 0)
    used_total = int(used_count.scalar_one() or 0)
    deleted_total = int(deleted_count.scalar_one() or 0)
    return {
        "memory_write_count": write_count,
        "memory_retrieval_count": retrieval_total,
        "memory_hit_rate": int((used_total / retrieval_total) * 100) if retrieval_total else 0,
        "memory_used_in_prompt_count": used_total,
        "memory_operation_count": int(operation_count.scalar_one() or 0),
        "memory_user_deleted_count": deleted_total,
        "memory_stale_count": int(stale_count.scalar_one() or 0),
        "memory_conflict_count": 0,
        "curator_merge_count": 0,
        "curator_dismiss_count": deleted_total,
        "recommendation_acceptance_rate": 0,
    }


async def _get_or_create_settings(
    db: AsyncSession, learner_id: uuid.UUID
) -> LearnerMemorySettings:
    result = await db.execute(
        select(LearnerMemorySettings).where(LearnerMemorySettings.learner_id == learner_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = LearnerMemorySettings(learner_id=learner_id)
        db.add(settings)
        await db.flush()
    return settings


def _settings_dict(settings: LearnerMemorySettings) -> dict[str, bool]:
    return {
        "emotion_rhythm_enabled": bool(settings.emotion_rhythm_enabled),
        "inferred_preferences_enabled": bool(settings.inferred_preferences_enabled),
        "low_confidence_memory_enabled": bool(settings.low_confidence_memory_enabled),
    }


async def _apply_memory_control(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    target_type: str,
    target_id: str,
    operation: str,
    content: str | None,
) -> tuple[dict, dict, str]:
    if target_type == "error_pattern":
        pattern = await _get_target(db, ErrorPattern, learner_id, target_id)
        before = {
            "skill": pattern.skill,
            "description": pattern.description,
            "status": pattern.status,
            "severity": pattern.severity,
        }
        if operation in {"delete", "disable"}:
            pattern.status = "dismissed"
        elif operation == "mark_improved":
            pattern.status = "improving"
            pattern.severity = "low"
            pattern.confidence = min(pattern.confidence or 0.5, 0.55)
        elif operation in {"edit", "correct"} and content:
            pattern.description = content
            pattern.status = "active"
            pattern.confidence = 1.0
        after = {
            "skill": pattern.skill,
            "description": pattern.description,
            "status": pattern.status,
            "severity": pattern.severity,
        }
        return before, after, pattern.status

    if target_type == "learning_memory_event":
        event = await _get_target(db, LearningMemoryEvent, learner_id, target_id)
        before = {"skill": event.skill, "visibility": event.visibility, "payload": event.payload or {}}
        if operation in {"delete", "disable"}:
            event.visibility = "deleted"
        elif operation in {"edit", "correct"} and content:
            payload = event.payload or {}
            payload["user_correction"] = content
            event.payload = payload
            event.created_by = "user"
        elif operation == "mark_improved":
            payload = event.payload or {}
            payload["user_marked_improved"] = True
            event.payload = payload
        after = {"skill": event.skill, "visibility": event.visibility, "payload": event.payload or {}}
        return before, after, event.visibility

    if target_type == "writing_phrase_mastery":
        mastery = await _get_target(db, WritingPhraseMastery, learner_id, target_id)
        before = {"skill": mastery.skill, "status": mastery.status, "confidence": mastery.confidence}
        if operation in {"delete", "disable"}:
            mastery.status = "dismissed"
        elif operation == "mark_improved":
            mastery.status = "mastered"
            mastery.confidence = max(mastery.confidence, 0.9)
        elif operation in {"edit", "correct"} and content:
            mastery.recommended_drill = content[:100]
            mastery.confidence = 1.0
        after = {
            "skill": mastery.skill,
            "status": mastery.status,
            "confidence": mastery.confidence,
            "recommended_drill": mastery.recommended_drill,
        }
        return before, after, mastery.status

    raise HTTPException(status_code=404, detail="Memory target type not found")


async def _get_target(db: AsyncSession, model, learner_id: uuid.UUID, target_id: str):
    try:
        parsed_id = uuid.UUID(target_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Memory item not found") from exc
    result = await db.execute(
        select(model).where(model.id == parsed_id, model.learner_id == learner_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return target
