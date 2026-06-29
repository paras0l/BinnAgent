import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.knowledge.exercise_grader import answer_to_text, grade_exercise_answer
from src.config import settings
from src.knowledge.exercises import ensure_unit_exercises
from src.knowledge.processor import process_uploaded_textbook
from src.knowledge.rag import retrieve_chunks
from src.memory.schemas import MemoryEventInput
from src.memory.explainer import MemoryExplainer
from src.memory.retriever import MemoryRetriever
from src.memory.writer import MemoryWriter
from src.models.knowledge import (
    CurriculumNode,
    ExerciseAttempt,
    ExerciseQuestion,
    KnowledgeLearningEvent,
    KnowledgePoint,
    KnowledgeSource,
    LearnerKnowledgeState,
)
from src.models.learner import Learner
from src.models.session import LearningSession, LearningTask
from src.models.vocabulary import ReviewSchedule, VocabularyItem
from src.providers.router import router as model_router
from src.vocabulary.learning import canonical_vocabulary_key, enroll_unit_vocabulary

router = APIRouter(tags=["knowledge-base"])


class LessonPartResponse(BaseModel):
    id: str
    title: str
    estimated_minutes: int
    completed: bool = False


class KnowledgeAttemptRequest(BaseModel):
    knowledge_point_id: uuid.UUID
    session_id: uuid.UUID | None = None
    correct: bool
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    hint_count: int = Field(default=0, ge=0, le=20)


class KnowledgeAttemptResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    status: str
    mastery_score: float
    exposure_count: int
    next_review_at: datetime


class StartLessonResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    parts: list[LessonPartResponse]
    knowledge_points: list[dict[str, Any]]
    vocabulary_enrollment: dict[str, int]


class CompleteLessonResponse(BaseModel):
    session_id: uuid.UUID
    completed_node_id: uuid.UUID
    next_node_id: uuid.UUID | None = None
    next_unit_title: str | None = None
    all_completed: bool = False


class UploadResponse(BaseModel):
    source_id: uuid.UUID
    filename: str
    status: Literal["uploaded", "processing"]
    message: str


class IngestResponse(BaseModel):
    source_id: uuid.UUID
    status: str
    page_count: int
    unit_count: int
    knowledge_count: int
    message: str


class ExerciseAnswerRequest(BaseModel):
    answer: str | dict[str, Any]
    session_id: uuid.UUID | None = None
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    hint_used: int = Field(default=0, ge=0, le=10)
    attempt_index: int = Field(default=0, ge=0, le=10)


class ExerciseAnswerResponse(BaseModel):
    question_id: uuid.UUID
    correct: bool
    score: float
    passed: bool
    answer: str
    explanation: str
    feedback: str
    hint: str | None = None
    can_retry: bool
    error_type: str | None = None
    next_review_signal: str
    rubric: dict[str, Any]


class KnowledgeReviewRequest(BaseModel):
    action: Literal["confirm", "update", "ignore"]
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1, max_length=1000)
    source_page: str | None = Field(default=None, min_length=1, max_length=30)
    note: str | None = Field(default=None, max_length=500)


class KnowledgeReviewResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    action: str
    status: str
    requires_review: bool


def _source_parser_payload(source: KnowledgeSource) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    parser_report = metadata.get("parser_report") or {}
    warnings = parser_report.get("warnings") or []
    if metadata.get("warning") and metadata["warning"] not in warnings:
        warnings = [*warnings, metadata["warning"]]
    return {
        "parser": metadata.get("parser"),
        "parser_profile": metadata.get("parser_profile"),
        "book_manifest_id": metadata.get("book_manifest_id"),
        "vocabulary_parser": metadata.get("vocabulary_parser"),
        "dictionary_enrichment": metadata.get("dictionary_enrichment"),
        "rag_chunk_count": metadata.get("rag_chunk_count", 0),
        "text_char_count": metadata.get("text_char_count", 0),
        "toc_fallback": bool(metadata.get("toc_fallback", False)),
        "warnings": warnings,
        "report": parser_report,
    }


def _review_item_payload(point: KnowledgePoint) -> dict[str, Any]:
    content = point.content or {}
    evidence = [
        f"来源页码：{point.source_page}",
        f"解析器：{content.get('origin', 'unknown')}",
    ]
    if content.get("raw_line"):
        evidence.append(f"原始行：{content['raw_line']}")
    warnings = content.get("warnings") or []
    return {
        "id": str(point.id),
        "title": point.title,
        "type": point.type,
        "summary": point.summary,
        "source_page": point.source_page,
        "unit_order": content.get("unit_order"),
        "raw_line": content.get("raw_line"),
        "confidence": content.get("confidence"),
        "warnings": warnings,
        "requires_review": bool(content.get("requires_review", False)),
        "parser": content.get("origin"),
        "status": point.status,
        "evidence": evidence,
    }


async def _ensure_learner(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _lesson_parts(points: list[KnowledgePoint]) -> list[dict[str, Any]]:
    labels: list[str] = []
    type_labels = {
        "vocabulary": "核心词汇",
        "grammar": "语法要点",
        "phrase": "重点词组",
        "sentence_pattern": "固定句式",
        "pronunciation": "核心语音",
        "text_note": "课文注释",
    }
    for point in points:
        label = type_labels.get(point.type, "知识讲解")
        if label not in labels:
            labels.append(label)
    labels = labels[:2]
    if not labels:
        labels.append("知识讲解")
    if len(labels) == 1:
        labels.append("知识巩固")
    labels.append("课本练习")
    minutes = [6, 6, 8]
    return [
        {
            "id": f"part-{index + 1}",
            "title": title,
            "estimated_minutes": minutes[index],
            "completed": False,
        }
        for index, title in enumerate(labels)
    ]


def _unit_point_filter(node: CurriculumNode):
    return or_(
        KnowledgePoint.curriculum_node_id == node.id,
        and_(
            KnowledgePoint.type == "grammar",
            KnowledgePoint.content["related_units"].contains([node.title]),
        ),
    )


def _unit_point_order():
    return (
        case((KnowledgePoint.type == "vocabulary", 0), else_=1),
        KnowledgePoint.content["unit_order"].as_integer().asc().nullslast(),
        KnowledgePoint.created_at.asc(),
    )


@router.get("/api/learners/{learner_id}/knowledge-base")
async def knowledge_base_overview(
    learner_id: uuid.UUID,
    node_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    source_result = await db.execute(
        select(KnowledgeSource)
        .where(
            KnowledgeSource.grade == "grade-7",
            KnowledgeSource.status.in_(["published", "review_required", "partial_indexed"]),
        )
        .order_by(KnowledgeSource.volume.asc(), KnowledgeSource.created_at.asc())
        .limit(1)
    )
    source = source_result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Published Grade 7 textbook not found")

    node_result = await db.execute(
        select(CurriculumNode)
        .where(CurriculumNode.source_id == source.id, CurriculumNode.parent_id.is_(None))
        .order_by(CurriculumNode.ordinal.asc())
    )
    nodes = list(node_result.scalars().all())
    if not nodes:
        raise HTTPException(status_code=409, detail="Textbook curriculum has not been generated")
    completed_task_result = await db.execute(
        select(LearningTask).where(
            LearningTask.learner_id == learner_id,
            LearningTask.skill == "knowledge",
            LearningTask.status == "completed",
        )
    )
    completed_node_ids: set[uuid.UUID] = set()
    for task in completed_task_result.scalars().all():
        if not task.input_ref or not task.input_ref.startswith("curriculum:"):
            continue
        try:
            completed_node_ids.add(uuid.UUID(task.input_ref.removeprefix("curriculum:")))
        except ValueError:
            continue

    recommended_node = next(
        (node for node in nodes if node.id not in completed_node_ids), nodes[-1]
    )
    if node_id is not None:
        display_node = next((node for node in nodes if node.id == node_id), None)
        if display_node is None:
            raise HTTPException(status_code=404, detail="Curriculum node not found in textbook")
    else:
        display_node = recommended_node

    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            _unit_point_filter(display_node),
            KnowledgePoint.status == "published",
        )
        .order_by(*_unit_point_order())
    )
    points = list(point_result.scalars().all())
    review_result = await db.execute(
        select(KnowledgePoint)
        .where(
            _unit_point_filter(display_node),
            KnowledgePoint.content["requires_review"].as_boolean().is_(True),
            KnowledgePoint.status.in_(["draft", "published"]),
        )
        .order_by(
            KnowledgePoint.content["confidence"].as_float().asc().nullsfirst(),
            *(_unit_point_order()),
        )
    )
    review_points = list(review_result.scalars().all())
    point_ids = [point.id for point in points]
    states: dict[uuid.UUID, LearnerKnowledgeState] = {}
    if point_ids:
        state_result = await db.execute(
            select(LearnerKnowledgeState).where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.knowledge_point_id.in_(point_ids),
            )
        )
        states = {item.knowledge_point_id: item for item in state_result.scalars().all()}

    progress = len(completed_node_ids.intersection({node.id for node in nodes})) / len(nodes)
    recommended_index = nodes.index(recommended_node)
    path_start = max(0, recommended_index - 1)
    path = []
    for node in nodes[path_start : path_start + 3]:
        path_status = (
            "completed"
            if node.id in completed_node_ids
            else "current"
            if node.id == recommended_node.id
            else "next"
        )
        path.append(
            {
                "id": str(node.id),
                "ordinal": node.ordinal,
                "title": node.title,
                "subtitle": node.subtitle or "",
                "status": path_status,
                "estimated_minutes": node.estimated_minutes or 20,
            }
        )
    memory_items = []
    try:
        memory_context = await MemoryRetriever(db).for_knowledge_exercise(
            learner_id=learner_id,
            limit=4,
        )
        memory_items = memory_context.loaded_items
    except Exception:
        memory_items = []

    return {
        "source": {
            "id": str(source.id),
            "title": source.title,
            "publisher": source.publisher or "人民教育出版社（PEP）",
            "edition": source.edition or "人教版",
            "status": source.status,
            "unit_count": source.unit_count,
            "knowledge_count": source.knowledge_count,
            "progress": progress,
            "requires_review": source.status == "review_required" or bool(review_points),
            "page_count": source.page_count,
        },
        "curriculum": [
            {
                "id": str(node.id),
                "parent_id": str(node.parent_id) if node.parent_id else None,
                "node_type": node.node_type,
                "title": node.title,
                "subtitle": node.subtitle,
                "ordinal": node.ordinal,
                "status": (
                    "completed"
                    if node.id in completed_node_ids
                    else "in_progress"
                    if node.id == recommended_node.id
                    else "available"
                ),
                "progress": 1.0 if node.id in completed_node_ids else 0.0,
                "estimated_minutes": node.estimated_minutes,
            }
            for node in nodes
        ],
        "current_node_id": str(display_node.id),
        "current_unit": {
            "id": str(display_node.id),
            "title": display_node.title,
            "subtitle": display_node.subtitle or "",
            "estimated_minutes": display_node.estimated_minutes or 20,
        },
        "daily_lesson": {
            "id": f"lesson-{display_node.id}",
            "title": f"{display_node.title} {display_node.subtitle or ''}".strip(),
            "estimated_minutes": display_node.estimated_minutes or 20,
            "parts": _lesson_parts(points),
        },
        "knowledge_points": [
            {
                "id": str(point.id),
                "title": point.title,
                "type": point.type,
                "summary": point.summary,
                "source_page": point.source_page,
                "unit_order": (point.content or {}).get("unit_order"),
                "requires_review": bool((point.content or {}).get("requires_review", False)),
                "warnings": (point.content or {}).get("warnings", []),
                "confidence": (point.content or {}).get("confidence"),
                "raw_line": (point.content or {}).get("raw_line"),
                "evidence": [
                    f"来源页码：{point.source_page}",
                    f"解析器：{(point.content or {}).get('origin', 'unknown')}",
                ],
                "mastery": states.get(point.id).mastery_score if point.id in states else 0.0,
            }
            for point in points
        ],
        "review": {
            "requires_review": source.status == "review_required" or bool(review_points),
            "pending_count": len(review_points),
            "low_confidence_count": sum(
                1 for point in review_points if ((point.content or {}).get("confidence") or 1) < 0.75
            ),
            "warning_count": sum(1 for point in review_points if (point.content or {}).get("warnings")),
            "items": [_review_item_payload(point) for point in review_points],
        },
        "parser_evidence": _source_parser_payload(source),
        "path": path,
        "recommendation_reason": MemoryExplainer().recommendation_reason(
            memory_items,
            f"已根据教材顺序和完成记录，为你推荐 {recommended_node.title}。",
        ),
    }


@router.patch(
    "/api/learners/{learner_id}/knowledge-base/review-items/{knowledge_point_id}",
    response_model=KnowledgeReviewResponse,
)
async def review_knowledge_point(
    learner_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    body: KnowledgeReviewRequest,
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeReviewResponse:
    await _ensure_learner(db, learner_id)
    point_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == knowledge_point_id)
    )
    point = point_result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")

    content = dict(point.content or {})
    if body.action == "ignore":
        point.status = "ignored"
        content["requires_review"] = False
        content["review_decision"] = "ignored"
    else:
        if body.title is not None:
            point.title = body.title.strip()
        if body.summary is not None:
            point.summary = body.summary.strip()
        if body.source_page is not None:
            point.source_page = body.source_page.strip()
        point.status = "published"
        content["requires_review"] = False
        content["review_decision"] = "updated" if body.action == "update" else "confirmed"

    if body.note:
        content["review_note"] = body.note.strip()
    content["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    content["reviewed_by_learner_id"] = str(learner_id)
    point.content = content
    await db.flush()
    remaining_result = await db.execute(
        select(func.count())
        .select_from(KnowledgePoint)
        .where(
            KnowledgePoint.source_id == point.source_id,
            KnowledgePoint.content["requires_review"].as_boolean().is_(True),
            KnowledgePoint.status.in_(["draft", "published"]),
        )
    )
    if int(remaining_result.scalar_one() or 0) == 0:
        source_result = await db.execute(
            select(KnowledgeSource).where(KnowledgeSource.id == point.source_id)
        )
        source = source_result.scalar_one_or_none()
        if source is not None and source.status == "review_required":
            source.status = "published"
    return KnowledgeReviewResponse(
        knowledge_point_id=point.id,
        action=body.action,
        status=point.status,
        requires_review=bool(content.get("requires_review", False)),
    )


@router.post(
    "/api/learners/{learner_id}/knowledge-base/lessons/{curriculum_node_id}/start",
    response_model=StartLessonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_knowledge_lesson(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> StartLessonResponse:
    await _ensure_learner(db, learner_id)
    node_result = await db.execute(
        select(CurriculumNode).where(CurriculumNode.id == curriculum_node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")
    point_result = await db.execute(
        select(KnowledgePoint)
        .where(_unit_point_filter(node), KnowledgePoint.status == "published")
        .order_by(*_unit_point_order())
    )
    points = list(point_result.scalars().all())
    lesson_parts = _lesson_parts(points)
    enrollment = await enroll_unit_vocabulary(db, learner_id, node)

    now = datetime.now(timezone.utc)
    session = LearningSession(
        learner_id=learner_id,
        session_type="textbook_lesson",
        active_skill="knowledge",
        today_goal=f"学习 {node.title} {node.subtitle or ''}".strip(),
        status="in_progress",
        started_at=now,
    )
    db.add(session)
    await db.flush()
    for part in lesson_parts:
        db.add(
            LearningTask(
                learner_id=learner_id,
                session_id=session.id,
                task_type="textbook_knowledge",
                skill="knowledge",
                title=part["title"],
                estimated_minutes=part["estimated_minutes"],
                status="pending",
                input_ref=f"curriculum:{node.id}",
            )
        )
    return StartLessonResponse(
        session_id=session.id,
        title=f"{node.title} {node.subtitle or ''}".strip(),
        parts=[LessonPartResponse(**part) for part in lesson_parts],
        knowledge_points=[
            {
                "id": str(point.id),
                "title": point.title,
                "summary": point.summary,
                "type": point.type,
            }
            for point in points
        ],
        vocabulary_enrollment={
            "total": enrollment.total,
            "newly_added": enrollment.newly_added,
            "source_linked": enrollment.source_linked,
            "already_known": enrollment.already_known,
        },
    )


@router.post(
    "/api/learners/{learner_id}/knowledge-base/lessons/{session_id}/complete",
    response_model=CompleteLessonResponse,
)
async def complete_knowledge_lesson(
    learner_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CompleteLessonResponse:
    await _ensure_learner(db, learner_id)
    session_result = await db.execute(
        select(LearningSession).where(
            LearningSession.id == session_id,
            LearningSession.learner_id == learner_id,
            LearningSession.active_skill == "knowledge",
        )
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Knowledge lesson session not found")

    task_result = await db.execute(
        select(LearningTask).where(LearningTask.session_id == session.id)
    )
    tasks = list(task_result.scalars().all())
    curriculum_ref = next(
        (
            task.input_ref
            for task in tasks
            if task.input_ref and task.input_ref.startswith("curriculum:")
        ),
        None,
    )
    if curriculum_ref is None:
        raise HTTPException(status_code=409, detail="Lesson is missing curriculum reference")
    try:
        completed_node_id = uuid.UUID(curriculum_ref.removeprefix("curriculum:"))
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail="Lesson curriculum reference is invalid"
        ) from exc

    node_result = await db.execute(
        select(CurriculumNode).where(CurriculumNode.id == completed_node_id)
    )
    completed_node = node_result.scalar_one_or_none()
    if completed_node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")

    next_result = await db.execute(
        select(CurriculumNode)
        .where(
            CurriculumNode.source_id == completed_node.source_id,
            CurriculumNode.parent_id.is_(None),
            CurriculumNode.ordinal > completed_node.ordinal,
        )
        .order_by(CurriculumNode.ordinal.asc())
        .limit(1)
    )
    next_node = next_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.completed_at = now
    session.summary = (
        f"完成教材课程：{completed_node.title} {completed_node.subtitle or ''}".strip()
    )
    for task in tasks:
        task.status = "completed"
        task.completed_at = now
    await db.flush()

    return CompleteLessonResponse(
        session_id=session.id,
        completed_node_id=completed_node.id,
        next_node_id=next_node.id if next_node else None,
        next_unit_title=(
            f"{next_node.title} {next_node.subtitle or ''}".strip() if next_node else None
        ),
        all_completed=next_node is None,
    )


@router.post(
    "/api/learners/{learner_id}/knowledge-base/attempts",
    response_model=KnowledgeAttemptResponse,
)
async def record_knowledge_attempt(
    learner_id: uuid.UUID,
    body: KnowledgeAttemptRequest,
    db: AsyncSession = Depends(get_db_session),
) -> KnowledgeAttemptResponse:
    await _ensure_learner(db, learner_id)
    point_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == body.knowledge_point_id)
    )
    point = point_result.scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")

    state_result = await db.execute(
        select(LearnerKnowledgeState).where(
            LearnerKnowledgeState.learner_id == learner_id,
            LearnerKnowledgeState.knowledge_point_id == point.id,
        )
    )
    learner_state = state_result.scalar_one_or_none()
    if learner_state is None:
        learner_state = LearnerKnowledgeState(
            learner_id=learner_id,
            knowledge_point_id=point.id,
            status="learning",
            mastery_score=0.0,
            confidence=0.0,
            exposure_count=0,
            correct_count=0,
            evidence_summary={},
        )
        db.add(learner_state)

    now = datetime.now(timezone.utc)
    previous_mastery = learner_state.mastery_score or 0.0
    change = 0.18 if body.correct else -0.12
    if body.hint_count:
        change -= min(body.hint_count * 0.02, 0.08)
    mastery = min(1.0, max(0.0, previous_mastery + change))
    learner_state.mastery_score = mastery
    learner_state.confidence = min(1.0, 0.2 + (learner_state.exposure_count + 1) * 0.12)
    learner_state.exposure_count = (learner_state.exposure_count or 0) + 1
    learner_state.correct_count = (learner_state.correct_count or 0) + int(body.correct)
    learner_state.status = (
        "mastered" if mastery >= 0.8 else "reviewing" if not body.correct else "learning"
    )
    learner_state.last_seen_at = now
    learner_state.next_review_at = now + timedelta(days=4 if body.correct else 1)
    learner_state.evidence_summary = {
        "last_result": "correct" if body.correct else "incorrect",
        "response_time_ms": body.response_time_ms,
        "hint_count": body.hint_count,
    }

    db.add(
        KnowledgeLearningEvent(
            learner_id=learner_id,
            session_id=body.session_id,
            event_type="knowledge_practiced",
            knowledge_point_id=point.id,
            payload={
                "correct": body.correct,
                "response_time_ms": body.response_time_ms,
                "hint_count": body.hint_count,
                "mastery_before": previous_mastery,
                "mastery_after": mastery,
            },
            occurred_at=now,
        )
    )
    await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="knowledge_point_practiced",
            skill="knowledge",
            subskill=point.type,
            source_type="knowledge_point",
            source_id=str(point.id),
            session_id=body.session_id,
            payload={
                "knowledge_point_id": str(point.id),
                "title": point.title,
                "point_type": point.type,
                "correct": body.correct,
                "mastery_before": previous_mastery,
                "mastery_after": mastery,
                "hint_count": body.hint_count,
                "response_time_ms": body.response_time_ms,
            },
            confidence=0.95,
            occurred_at=now,
        )
    )
    db.add(
        ReviewSchedule(
            learner_id=learner_id,
            item_type="knowledge",
            item_id=point.id,
            scheduled_at=learner_state.next_review_at,
            result="correct" if body.correct else "incorrect",
            response_time_ms=body.response_time_ms,
            confidence_before=previous_mastery,
            confidence_after=mastery,
            recommended_next_drill="textbook_review",
        )
    )

    if point.type == "vocabulary":
        vocab_result = await db.execute(
            select(VocabularyItem).where(
                VocabularyItem.learner_id == learner_id,
                func.lower(VocabularyItem.word) == point.title.lower(),
            )
        )
        vocab = vocab_result.scalar_one_or_none()
        if vocab is None:
            db.add(
                VocabularyItem(
                    learner_id=learner_id,
                    word=point.title,
                    canonical_key=canonical_vocabulary_key(point.title),
                    entry_kind=(point.content or {}).get("entry_kind") or "word",
                    preferred_accent="auto",
                    level="grade-7",
                    meanings=[point.summary],
                    source_ref=f"knowledge:{point.id}",
                    status="learning",
                    confidence=mastery,
                    next_review_at=learner_state.next_review_at,
                )
            )
        else:
            vocab.confidence = mastery
            vocab.next_review_at = learner_state.next_review_at

    await db.flush()
    return KnowledgeAttemptResponse(
        knowledge_point_id=point.id,
        status=learner_state.status,
        mastery_score=mastery,
        exposure_count=learner_state.exposure_count,
        next_review_at=learner_state.next_review_at,
    )


def _is_grade7_filename(filename: str) -> bool:
    normalized = filename.casefold().replace("_", "-")
    return any(token in normalized for token in ("七年级", "7年级", "grade-7", "grade7"))


@router.post(
    "/api/knowledge/sources/uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_knowledge_source(
    request: Request,
    learner_id: uuid.UUID = Query(),
    filename: str = Query(min_length=1, max_length=500),
    db: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    await _ensure_learner(db, learner_id)
    safe_filename = Path(filename).name
    if not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="仅支持 PDF 教材")
    if not _is_grade7_filename(safe_filename):
        raise HTTPException(status_code=422, detail="当前仅支持七年级教材，请检查文件名")
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/pdf":
        raise HTTPException(status_code=415, detail="Content-Type 必须为 application/pdf")

    data = await request.body()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="文件不是有效的 PDF")
    if len(data) > settings.knowledge_max_upload_bytes:
        raise HTTPException(status_code=413, detail="PDF 不能超过 50 MB")

    digest = hashlib.sha256(data).hexdigest()
    duplicate_result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.sha256 == digest,
            or_(
                KnowledgeSource.owner_learner_id == learner_id,
                KnowledgeSource.visibility == "public",
            ),
        )
    )
    duplicate = duplicate_result.scalar_one_or_none()
    if duplicate is not None:
        return UploadResponse(
            source_id=duplicate.id,
            filename=duplicate.filename,
            status="uploaded" if duplicate.status == "uploaded" else "processing",
            message="该教材已存在，已复用现有知识版本。",
        )

    upload_dir = Path(settings.knowledge_upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{digest}.pdf"
    destination.write_bytes(data)
    source = KnowledgeSource(
        owner_learner_id=learner_id,
        title=safe_filename.removesuffix(".pdf"),
        filename=safe_filename,
        publisher=None,
        edition=None,
        grade="grade-7",
        volume="lower" if "下册" in safe_filename else "upper" if "上册" in safe_filename else None,
        status="uploaded",
        visibility="private",
        object_key=str(destination),
        sha256=digest,
        file_size=len(data),
        unit_count=0,
        knowledge_count=0,
        metadata_={"stage": "uploaded"},
    )
    db.add(source)
    await db.flush()
    return UploadResponse(
        source_id=source.id,
        filename=source.filename,
        status="uploaded",
        message="教材上传成功，已进入知识生成流程。",
    )


@router.post("/api/knowledge/sources/{source_id}/ingest", response_model=IngestResponse)
async def ingest_knowledge_source(
    source_id: uuid.UUID,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> IngestResponse:
    await _ensure_learner(db, learner_id)
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    if source.owner_learner_id not in (None, learner_id):
        raise HTTPException(status_code=403, detail="无权处理该教材")
    if source.status == "published":
        return IngestResponse(
            source_id=source.id,
            status=source.status,
            page_count=source.page_count or 0,
            unit_count=source.unit_count,
            knowledge_count=source.knowledge_count,
            message="已复用发布中的教材知识。",
        )
    try:
        source.status = "processing"
        await db.flush()
        parsed = await process_uploaded_textbook(db, source)
    except Exception as exc:
        source.status = "failed"
        source.metadata_ = {"stage": "failed", "error": str(exc)[:500]}
        raise HTTPException(status_code=422, detail="PDF 解析失败，请检查文件或稍后重试") from exc
    return IngestResponse(
        source_id=source.id,
        status=source.status,
        page_count=parsed.page_count,
        unit_count=source.unit_count,
        knowledge_count=source.knowledge_count,
        message="教材解析完成，知识草稿等待审核发布。",
    )


@router.get("/api/knowledge/search")
async def search_knowledge_chunks(
    learner_id: uuid.UUID,
    query: str = Query(min_length=2, max_length=500),
    source_id: uuid.UUID | None = None,
    curriculum_node_id: uuid.UUID | None = None,
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    chunks = await retrieve_chunks(
        db,
        model_router,
        query=query,
        source_id=source_id,
        curriculum_node_id=curriculum_node_id,
        limit=limit,
    )
    mode = chunks[0].retrieval_mode if chunks else "fallback"
    return {
        "query": query,
        "mode": mode,
        "retrieval": {
            "mode": mode,
            "embedding_model": (
                chunks[0].embedding_model if chunks else settings.ollama_embedding_model
            ),
            "chunk_version": chunks[0].chunk_version if chunks else None,
            "source_version": chunks[0].source_version if chunks else None,
        },
        "results": [
            {
                "chunk_id": str(chunk.chunk_id),
                "source_id": str(chunk.source_id),
                "curriculum_node_id": (
                    str(chunk.curriculum_node_id) if chunk.curriculum_node_id else None
                ),
                "page_number": chunk.page_number,
                "content": chunk.content,
                "score": round(chunk.score, 4),
                "mode": chunk.retrieval_mode,
                "embedding_model": chunk.embedding_model,
                "chunk_version": chunk.chunk_version,
                "source_version": chunk.source_version,
            }
            for chunk in chunks
        ],
    }


@router.post("/api/learners/{learner_id}/knowledge-base/units/{curriculum_node_id}/exercises")
async def start_unit_exercises(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    limit: int = Query(default=8, ge=1, le=12),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    node_result = await db.execute(
        select(CurriculumNode).where(CurriculumNode.id == curriculum_node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")
    questions = await ensure_unit_exercises(
        db,
        source_id=node.source_id,
        curriculum_node_id=node.id,
    )
    return {
        "curriculum_node_id": str(node.id),
        "title": f"{node.title} 练习",
        "questions": [
            {
                "id": str(question.id),
                "question_type": question.question_type,
                "stem": question.stem,
                "options": question.options or [],
                "difficulty": question.difficulty,
                "metadata": question.metadata_ or {},
            }
            for question in questions[:limit]
        ],
    }


@router.post(
    "/api/learners/{learner_id}/knowledge-base/exercises/{question_id}/attempts",
    response_model=ExerciseAnswerResponse,
)
async def submit_exercise_attempt(
    learner_id: uuid.UUID,
    question_id: uuid.UUID,
    body: ExerciseAnswerRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExerciseAnswerResponse:
    await _ensure_learner(db, learner_id)
    result = await db.execute(
        select(ExerciseQuestion).where(
            ExerciseQuestion.id == question_id,
            ExerciseQuestion.status == "published",
        )
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Exercise question not found")
    submitted_answer = answer_to_text(body.answer)
    if not submitted_answer:
        raise HTTPException(status_code=422, detail="Answer cannot be empty")
    grading = grade_exercise_answer(question, body.answer, attempt_index=body.attempt_index)
    correct = bool(grading["correct"])
    stored_answer = body.answer if isinstance(body.answer, str) else json.dumps(body.answer, ensure_ascii=False)
    db.add(
        ExerciseAttempt(
            learner_id=learner_id,
            question_id=question.id,
            session_id=body.session_id,
            submitted_answer=stored_answer.strip(),
            correct=correct,
            response_time_ms=body.response_time_ms,
        )
    )
    if question.knowledge_point_id:
        now = datetime.now(timezone.utc)
        db.add(
            KnowledgeLearningEvent(
                learner_id=learner_id,
                session_id=body.session_id,
                event_type="exercise_answered",
                knowledge_point_id=question.knowledge_point_id,
                payload={
                    "question_id": str(question.id),
                    "question_type": question.question_type,
                    "correct": correct,
                    "score": grading["score"],
                    "passed": grading["passed"],
                    "error_type": grading["error_type"],
                    "hint_used": body.hint_used,
                    "attempt_index": body.attempt_index,
                    "response_time_ms": body.response_time_ms,
                    "next_review_signal": grading["next_review_signal"],
                },
                occurred_at=now,
            )
        )
        await MemoryWriter(db).record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type="knowledge_exercise_answered",
                skill="knowledge",
                subskill=question.question_type,
                source_type="exercise_attempt",
                source_id=str(question.id),
                session_id=body.session_id,
                payload={
                    "question_id": str(question.id),
                    "knowledge_point_id": str(question.knowledge_point_id),
                    "question_type": question.question_type,
                    "correct": correct,
                    "score": grading["score"],
                    "passed": grading["passed"],
                    "error_type": grading["error_type"],
                    "hint_used": body.hint_used,
                    "attempt_index": body.attempt_index,
                    "response_time_ms": body.response_time_ms,
                    "next_review_signal": grading["next_review_signal"],
                },
                confidence=0.95,
                occurred_at=now,
            )
        )
    await db.flush()
    return ExerciseAnswerResponse(
        question_id=question.id,
        correct=correct,
        score=grading["score"],
        passed=grading["passed"],
        answer=question.answer,
        explanation=question.explanation,
        feedback=grading["feedback"],
        hint=grading["hint"],
        can_retry=grading["can_retry"],
        error_type=grading["error_type"],
        next_review_signal=grading["next_review_signal"],
        rubric=grading["rubric"],
    )
