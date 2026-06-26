import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.explainer import MemoryExplainer
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.knowledge import CurriculumNode, KnowledgePoint
from src.models.learner import Learner
from src.models.vocabulary import (
    VocabularyAttempt,
    VocabularyItem,
    VocabularyItemSource,
    VocabularyMasteryVector,
    VocabularyPracticeSession,
    VocabularyUserOverride,
)
from src.tools.pronunciation import lookup_pronunciations
from src.vocabulary.learning import (
    canonical_vocabulary_key,
    current_item_id,
    enroll_unit_vocabulary,
    excluded_item_ids,
    mastery_to_dict,
    record_attempt,
    spelling_feedback,
)

router = APIRouter(prefix="/api/learners/{learner_id}/vocabulary", tags=["vocabulary-learning"])
learning_router = APIRouter(
    prefix="/api/learners/{learner_id}/vocabulary-learning",
    tags=["vocabulary-learning"],
)


class StartPracticeRequest(BaseModel):
    mode: Literal["new", "review", "spelling"]
    prompt_mode: Literal["audio", "meaning", "context"] = "audio"
    accent: Literal["uk", "us", "auto"] = "uk"
    curriculum_node_id: uuid.UUID | None = None
    limit: int = Field(default=10, ge=1, le=500)


class StartPracticeResponse(BaseModel):
    session_id: uuid.UUID
    mode: str
    total: int
    current_index: int


class AttemptRequest(BaseModel):
    vocabulary_item_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=80)
    action: Literal["submit", "reveal"] = "submit"
    answer: str | None = Field(default=None, max_length=255)
    rating: int | None = Field(default=None, ge=1, le=4)
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    hint_count: int = Field(default=0, ge=0, le=3)
    replay_count: int = Field(default=0, ge=0, le=50)


class AdvanceRequest(BaseModel):
    vocabulary_item_id: uuid.UUID


async def _ensure_learner(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


async def _get_session(
    db: AsyncSession, learner_id: uuid.UUID, session_id: uuid.UUID
) -> VocabularyPracticeSession:
    result = await db.execute(
        select(VocabularyPracticeSession).where(
            VocabularyPracticeSession.id == session_id,
            VocabularyPracticeSession.learner_id == learner_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Vocabulary practice session not found")
    return session


async def _sources_for_item(
    db: AsyncSession, learner_id: uuid.UUID, item_id: uuid.UUID
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(VocabularyItemSource).where(
            VocabularyItemSource.learner_id == learner_id,
            VocabularyItemSource.vocabulary_item_id == item_id,
            VocabularyItemSource.active.is_(True),
        )
    )
    return [
        {
            "type": source.source_type,
            "label": source.display_label,
            "reason": source.reason,
            "priority": source.priority,
            "context": source.context_snapshot or {},
        }
        for source in result.scalars().all()
    ]


async def _override_for_item(
    db: AsyncSession, learner_id: uuid.UUID, item_id: uuid.UUID
) -> VocabularyUserOverride | None:
    result = await db.execute(
        select(VocabularyUserOverride).where(
            VocabularyUserOverride.learner_id == learner_id,
            VocabularyUserOverride.vocabulary_item_id == item_id,
        )
    )
    return result.scalar_one_or_none()


async def _mastery_for_item(
    db: AsyncSession, learner_id: uuid.UUID, item_id: uuid.UUID
) -> VocabularyMasteryVector | None:
    result = await db.execute(
        select(VocabularyMasteryVector).where(
            VocabularyMasteryVector.learner_id == learner_id,
            VocabularyMasteryVector.vocabulary_item_id == item_id,
        )
    )
    return result.scalar_one_or_none()


def _meaning_id(meaning: Any, index: int) -> str:
    if isinstance(meaning, dict):
        for key in ("id", "sense_id", "key"):
            value = meaning.get(key)
            if isinstance(value, str) and value:
                return value
    return str(index)


def _visible_meanings(item: VocabularyItem, override: VocabularyUserOverride | None) -> list[Any]:
    meanings = item.meanings if isinstance(item.meanings, list) else []
    hidden = set(override.hidden_meaning_ids if override else [])
    visible = [
        meaning for index, meaning in enumerate(meanings)
        if _meaning_id(meaning, index) not in hidden
    ]
    user_meanings = override.meaning_overrides if override and isinstance(override.meaning_overrides, list) else []
    return [meaning for meaning in user_meanings if _is_active_override(meaning)] + visible


def _is_active_override(value: Any) -> bool:
    return not isinstance(value, dict) or value.get("active", True) is not False


def _effective_examples(item: VocabularyItem, override: VocabularyUserOverride | None) -> list[Any]:
    user_examples = override.user_examples if override and isinstance(override.user_examples, list) else []
    system_examples = item.examples if isinstance(item.examples, list) else []
    return user_examples + system_examples


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("definition_zh", "definition", "meaning", "text", "zh", "content"):
                text = first.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


def _part_of_speech(item: VocabularyItem) -> str:
    if isinstance(item.meanings, list) and item.meanings and isinstance(item.meanings[0], dict):
        value = item.meanings[0].get("part_of_speech") or item.meanings[0].get("pos")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return {
        "phrase": "短语",
        "proper_noun": "专有名词",
        "abbreviation": "缩写",
    }.get(item.entry_kind, "单词")


def _blank_example(item: VocabularyItem) -> str | None:
    example = _first_text(item.examples)
    if not example:
        return None
    return re.sub(re.escape(item.word), "___", example, count=1, flags=re.IGNORECASE)


def _blank_example_from_text(item: VocabularyItem, example: str | None) -> str | None:
    if not example:
        return None
    return re.sub(re.escape(item.word), "___", example, count=1, flags=re.IGNORECASE)


def _summary(session: VocabularyPracticeSession) -> dict[str, Any]:
    total = len(session.item_ids)
    return {
        "session_id": str(session.id),
        "status": session.status,
        "total": total,
        "completed": min(session.current_index, total),
        "correct": session.correct_count,
        "hinted": session.hinted_count,
        "revealed": session.revealed_count,
        "due_next": max(0, total - session.current_index),
    }


@router.get("/units/{curriculum_node_id}/summary")
async def unit_vocabulary_summary(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    total_result = await db.execute(
        select(func.count())
        .select_from(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == curriculum_node_id,
            KnowledgePoint.type == "vocabulary",
            KnowledgePoint.status == "published",
            KnowledgePoint.content["role"].as_string() == "unit_wordlist",
        )
    )
    total = total_result.scalar_one()
    result = await db.execute(
        select(VocabularyItem, VocabularyItemSource)
        .join(VocabularyItemSource, VocabularyItemSource.vocabulary_item_id == VocabularyItem.id)
        .where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItemSource.curriculum_node_id == curriculum_node_id,
            VocabularyItemSource.active.is_(True),
        )
    )
    rows = result.all()
    unenrolled = max(0, total - len(rows))
    return {
        "unit_id": str(curriculum_node_id),
        "total": total,
        "enrolled": len(rows),
        "new": unenrolled + sum(item.review_count == 0 for item, _ in rows),
        "learning": sum(item.status in {"learning", "reviewing"} for item, _ in rows),
        "mastered": sum(item.status == "mastered" for item, _ in rows),
        "due": sum(
            item.next_review_at and item.next_review_at <= datetime.now(timezone.utc)
            for item, _ in rows
        ),
    }


@router.get("/items/{item_id}/pronunciations")
async def item_pronunciations(
    learner_id: uuid.UUID,
    item_id: uuid.UUID,
    accent: Literal["uk", "us", "auto"] = Query(default="uk"),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.id == item_id,
            VocabularyItem.learner_id == learner_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    assets = await lookup_pronunciations(item.word, "uk" if accent == "auto" else accent)
    return {
        "vocabulary_item_id": str(item.id),
        "word": item.word,
        "assets": [asset.__dict__ for asset in assets],
        "tts_text": item.word if all(asset.audio_url is None for asset in assets) else None,
    }


@router.post("/units/{curriculum_node_id}/enroll")
async def enroll_unit(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    node_result = await db.execute(
        select(CurriculumNode).where(CurriculumNode.id == curriculum_node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")
    enrolled = await enroll_unit_vocabulary(db, learner_id, node)
    return {"unit_id": str(node.id), **enrolled.__dict__}


@router.post("/sessions", response_model=StartPracticeResponse, status_code=status.HTTP_201_CREATED)
async def start_practice_session(
    learner_id: uuid.UUID,
    body: StartPracticeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StartPracticeResponse:
    await _ensure_learner(db, learner_id)
    excluded_ids = await excluded_item_ids(db, learner_id)
    now = datetime.now(timezone.utc)
    if body.curriculum_node_id:
        node_result = await db.execute(
            select(CurriculumNode).where(CurriculumNode.id == body.curriculum_node_id)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            raise HTTPException(status_code=404, detail="Curriculum node not found")
        await enroll_unit_vocabulary(db, learner_id, node)
        query = (
            select(VocabularyItem)
            .join(
                VocabularyItemSource, VocabularyItemSource.vocabulary_item_id == VocabularyItem.id
            )
            .where(
                VocabularyItem.learner_id == learner_id,
                VocabularyItemSource.curriculum_node_id == body.curriculum_node_id,
                VocabularyItemSource.active.is_(True),
            )
        )
        if body.mode == "new":
            query = query.where(VocabularyItem.review_count == 0)
        elif body.mode in {"review", "spelling"}:
            query = query.where(
                VocabularyItem.status != "mastered",
                VocabularyItem.next_review_at <= now,
            )
        if excluded_ids:
            query = query.where(VocabularyItem.id.not_in(excluded_ids))
        source_item_result = await db.execute(
            query.order_by(
                VocabularyItem.review_count.asc(),
                VocabularyItem.next_review_at.asc().nullsfirst(),
                VocabularyItem.created_at.asc(),
            ).limit(body.limit)
        )
        items = list(source_item_result.scalars().unique().all())
    else:
        conditions = [VocabularyItem.learner_id == learner_id]
        if body.mode == "new":
            conditions.append(VocabularyItem.review_count == 0)
        else:
            conditions.extend([VocabularyItem.status != "mastered", VocabularyItem.next_review_at <= now])
        if excluded_ids:
            conditions.append(VocabularyItem.id.not_in(excluded_ids))
        item_result = await db.execute(
            select(VocabularyItem)
            .where(*conditions)
            .order_by(
                VocabularyItem.review_count.asc(),
                VocabularyItem.next_review_at.asc().nullsfirst(), VocabularyItem.created_at.asc()
            )
            .limit(body.limit)
        )
        items = list(item_result.scalars().all())
    if not items:
        raise HTTPException(
            status_code=409, detail="当前没有可练习的词汇，请先开启教材单元或添加单词"
        )
    session = VocabularyPracticeSession(
        learner_id=learner_id,
        mode=body.mode,
        prompt_mode=body.prompt_mode,
        accent=body.accent,
        curriculum_node_id=body.curriculum_node_id,
        status="in_progress",
        item_ids=[str(item.id) for item in items],
        current_index=0,
        correct_count=0,
        hinted_count=0,
        revealed_count=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    return StartPracticeResponse(
        session_id=session.id,
        mode=session.mode,
        total=len(items),
        current_index=0,
    )


@learning_router.post("/new-session", response_model=StartPracticeResponse, status_code=status.HTTP_201_CREATED)
async def start_new_learning_session(
    learner_id: uuid.UUID,
    body: StartPracticeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StartPracticeResponse:
    body.mode = "new"
    body.prompt_mode = "context"
    return await start_practice_session(learner_id, body, db)


@learning_router.post("/review-session", response_model=StartPracticeResponse, status_code=status.HTTP_201_CREATED)
async def start_review_learning_session(
    learner_id: uuid.UUID,
    body: StartPracticeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StartPracticeResponse:
    body.mode = "review"
    body.prompt_mode = "meaning"
    return await start_practice_session(learner_id, body, db)


@router.get("/sessions/{session_id}/next")
async def next_practice_task(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    session = await _get_session(db, learner_id, session_id)
    item_id = current_item_id(session)
    if item_id is None:
        session.status = "completed"
        session.completed_at = session.completed_at or datetime.now(timezone.utc)
        return {"completed": True, "summary": _summary(session)}
    item_result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.id == item_id,
            VocabularyItem.learner_id == learner_id,
        )
    )
    item = item_result.scalar_one()
    override = await _override_for_item(db, learner_id, item.id)
    mastery = await _mastery_for_item(db, learner_id, item.id)
    sources = await _sources_for_item(db, learner_id, item.id)
    assets = await lookup_pronunciations(
        item.word, session.accent if session.accent != "auto" else "uk"
    )
    memory_items = []
    try:
        memory_context = await MemoryRetriever(db).retrieve_context(
            learner_id=learner_id,
            reason="vocabulary_practice",
            skill="vocabulary",
            limit=3,
        )
        memory_items = memory_context.loaded_items
    except Exception:
        memory_items = []
    effective_word = override.display_form_override if override and override.display_form_override else item.word
    meanings = _visible_meanings(item, override)
    examples = _effective_examples(item, override)
    first_example = _first_text(examples)
    payload: dict[str, Any] = {
        "completed": False,
        "session_id": str(session.id),
        "mode": session.mode,
        "vocabulary_item_id": str(item.id),
        "current_index": session.current_index,
        "total": len(session.item_ids),
        "prompt_mode": session.prompt_mode,
        "answer_length": len(item.canonical_key),
        "phonetic": item.phonetic,
        "phonetic_uk": item.phonetic_uk,
        "phonetic_us": item.phonetic_us,
        "audio_url": item.audio_url,
        "audio_uk": item.audio_uk,
        "audio_us": item.audio_us,
        "word": effective_word if session.mode in {"new", "review"} else None,
        "display_word": effective_word,
        "entry_kind": item.entry_kind,
        "dictionary_senses": item.dictionary_senses or [],
        "word_forms": item.word_forms or {},
        "dictionary_tags": item.dictionary_tags or [],
        "meanings": meanings,
        "examples": examples,
        "user_override": {
            "display_form_override": override.display_form_override if override else None,
            "user_understanding": override.user_understanding if override else None,
            "user_notes": override.user_notes if override else None,
            "review_preference": override.review_preference if override else "normal",
            "manual_mastery": override.manual_mastery if override else None,
        },
        "mastery": mastery_to_dict(mastery, item.confidence),
        "pronunciations": [asset.__dict__ for asset in assets],
        "tts_text": item.word if all(asset.audio_url is None for asset in assets) else None,
        "context_with_blank": _blank_example_from_text(item, first_example),
        "sources": sources,
        "part_of_speech": _part_of_speech(item),
        "recommendation_reason": MemoryExplainer().recommendation_reason(
            memory_items,
            "根据复习到期时间、掌握度和最近练习记录安排这道词汇任务。",
        ),
    }
    if session.mode in {"new", "review"}:
        payload.update(
            {
                "word": effective_word,
                "meaning": _first_text(meanings),
                "example": first_example,
                "show_answer_first": session.mode == "new",
                "allow_reveal": True,
            }
        )
    return payload


@router.post("/sessions/{session_id}/hint")
async def get_practice_hint(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    level: int = Query(ge=1, le=3),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    session = await _get_session(db, learner_id, session_id)
    item_id = current_item_id(session)
    if item_id is None:
        raise HTTPException(status_code=409, detail="Session is complete")
    result = await db.execute(select(VocabularyItem).where(VocabularyItem.id == item_id))
    item = result.scalar_one()
    if level == 1:
        override = await _override_for_item(db, learner_id, item.id)
        examples = _effective_examples(item, override)
        meanings = _visible_meanings(item, override)
        return {
            "level": 1,
            "hint": _blank_example_from_text(item, _first_text(examples)) or _first_text(meanings) or "再听一次发音",
        }
    if level == 2:
        return {"level": 2, "hint": f"首字母是 {item.word[:1]}，共 {len(item.word)} 个字符"}
    return {"level": 3, "hint": item.phonetic or f"结尾是 {item.word[-3:]}"}


@router.post("/sessions/{session_id}/attempts")
async def submit_practice_attempt(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AttemptRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    session = await _get_session(db, learner_id, session_id)
    if current_item_id(session) != body.vocabulary_item_id:
        raise HTTPException(status_code=409, detail="Attempt does not match the current task")
    existing_result = await db.execute(
        select(VocabularyAttempt).where(
            VocabularyAttempt.session_id == session.id,
            VocabularyAttempt.idempotency_key == body.idempotency_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    item_result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.id == body.vocabulary_item_id,
            VocabularyItem.learner_id == learner_id,
        )
    )
    item = item_result.scalar_one()
    if session.mode == "spelling":
        normalized = canonical_vocabulary_key(body.answer or "")
        if body.action == "reveal":
            result, score, error_type, diff, feedback = (
                "revealed",
                0.0,
                None,
                [],
                "先记住答案，稍后再巩固。",
            )
        else:
            if not normalized:
                raise HTTPException(status_code=422, detail="先试着拼一下")
            correct = item.canonical_key
            error_type, diff, feedback = spelling_feedback(normalized, correct)
            result = "correct" if error_type is None else "incorrect"
            score = 1.0 if result == "correct" else 0.0
    else:
        if body.rating is None:
            raise HTTPException(status_code=422, detail="Review rating is required")
        result = "correct" if body.rating >= 3 else "incorrect"
        score = body.rating / 4
        error_type, diff = None, []
        feedback = "已加入第一次复习计划" if session.mode == "new" else "已更新复习计划"
    if existing is None:
        existing = await record_attempt(
            db,
            session=session,
            item=item,
            idempotency_key=body.idempotency_key,
            drill_type=session.mode,
            answer=body.answer,
            result=result,
            score=score,
            error_type=error_type,
            letter_diff=diff,
            response_time_ms=body.response_time_ms,
            hint_count=body.hint_count,
            replay_count=body.replay_count,
        )
        await MemoryWriter(db).record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type="vocabulary_attempted",
                skill="vocabulary",
                subskill=session.mode,
                source_type="vocabulary_attempt",
                source_id=str(existing.id),
                payload={
                    "vocabulary_item_id": str(item.id),
                    "word": item.word,
                    "drill_type": existing.drill_type,
                    "result": existing.result,
                    "score": existing.score,
                    "error_type": existing.error_type,
                    "hint_count": existing.hint_count,
                    "replay_count": existing.replay_count,
                    "response_time_ms": existing.response_time_ms,
                    "practice_session_id": str(session.id),
                },
                confidence=0.95,
                occurred_at=existing.occurred_at,
            )
        )
        if existing.result in {"incorrect", "revealed"}:
            await MemoryWriter(db).record_event(
                MemoryEventInput(
                    learner_id=learner_id,
                    event_type="vocabulary_mistake_recorded",
                    skill="vocabulary",
                    subskill=existing.drill_type,
                    source_type="vocabulary_attempt",
                    source_id=str(existing.id),
                    payload={
                        "vocabulary_item_id": str(item.id),
                        "word": item.word,
                        "result": existing.result,
                        "error_type": existing.error_type or "needs_practice",
                    },
                    confidence=0.9,
                    occurred_at=existing.occurred_at,
                )
            )
    override = await _override_for_item(db, learner_id, item.id)
    meanings = _visible_meanings(item, override)
    examples = _effective_examples(item, override)
    return {
        "attempt_id": str(existing.id),
        "result": existing.result,
        "correct_answer": item.word,
        "phonetic": item.phonetic,
        "phonetic_uk": item.phonetic_uk,
        "phonetic_us": item.phonetic_us,
        "audio_url": item.audio_url,
        "audio_uk": item.audio_uk,
        "audio_us": item.audio_us,
        "dictionary_senses": item.dictionary_senses or [],
        "word_forms": item.word_forms or {},
        "dictionary_tags": item.dictionary_tags or [],
        "meanings": meanings,
        "examples": examples,
        "meaning": _first_text(meanings),
        "part_of_speech": _part_of_speech(item),
        "example": _first_text(examples),
        "error_type": existing.error_type,
        "letter_diff": existing.letter_diff or [],
        "feedback_text": feedback,
        "can_retry": existing.result == "incorrect",
    }


@router.post("/sessions/{session_id}/advance")
async def advance_practice_session(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AdvanceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    session = await _get_session(db, learner_id, session_id)
    if current_item_id(session) != body.vocabulary_item_id:
        raise HTTPException(status_code=409, detail="Advance does not match the current task")
    session.current_index += 1
    if session.current_index >= len(session.item_ids):
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return _summary(session)


@router.get("/sessions/{session_id}/summary")
async def practice_summary(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return _summary(await _get_session(db, learner_id, session_id))
