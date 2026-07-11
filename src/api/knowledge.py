import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.knowledge.exercise_grader import answer_to_text, grade_exercise_answer
from src.config import settings
from src.db import async_session_factory
from src.evidence.resolver import evidence_from_attempt, evidence_from_memory_event
from src.evidence.types import EvidenceRef
from src.exercises import ExerciseAttemptService
from src.exercises.item_mapper import exercise_question_to_item
from src.knowledge.exercise_pool import ExercisePoolSnapshot, get_exercise_pool
from src.knowledge.unit_exercise_generation import select_unit_exercises_for_learner
from src.knowledge.processor import process_uploaded_textbook
from src.knowledge.quality import availability_status_for_quality, quality_summary, score_textbook_quality
from src.knowledge.rag import retrieve_chunks
from src.knowledge.review_queue import (
    apply_quality_gate,
    mark_target_reviewed,
    queue_summary,
    recalculate_quality_gate_from_queue,
)
from src.mastery.engine import MasteryEngine
from src.mastery.types import AttemptSignal
from src.memory.schemas import MemoryEventInput
from src.memory.explainer import MemoryExplainer
from src.memory.retriever import MemoryRetriever
from src.memory.writer import MemoryWriter
from src.models.knowledge import (
    CurriculumNode,
    ExerciseQuestion,
    KnowledgeChunk,
    KnowledgeLearningEvent,
    KnowledgePoint,
    KnowledgeSource,
    LearnerKnowledgeState,
    ParserReviewItem,
    ParserRun,
)
from src.models.learner import Learner
from src.models.learning_progress import LearningProgressItem
from src.models.session import LearningSession, LearningTask
from src.models.vocabulary import ReviewSchedule, VocabularyItem, VocabularyItemSource
from src.providers.router import router as model_router
from src.runtime.episode import EpisodeRuntime
from src.runtime.hashing import stable_json_hash
from src.runtime.schemas import EpisodeTraceView, episode_to_view, event_to_view, tool_call_to_view
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy
from src.verification.report import verify_knowledge_exercise_episode
from src.vocabulary.learning import (
    canonical_vocabulary_key,
    enroll_unit_vocabulary,
    is_unit_wordlist_point,
    learnable_point_statuses,
)

router = APIRouter(tags=["knowledge-base"])

STALE_INGEST_METADATA_KEYS = {
    "blocking_reasons",
    "document_quality",
    "error",
    "parser_report",
    "parser_report_summary",
    "parse_quality_status",
    "quality_score",
    "quality_status",
    "warning",
}


def _clear_stale_ingest_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(metadata)
    for key in STALE_INGEST_METADATA_KEYS:
        cleaned.pop(key, None)
    return cleaned


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


class UpdateUnitProgressRequest(BaseModel):
    action: Literal["skip", "relearn"]


class UnitProgressResponse(BaseModel):
    curriculum_node_id: uuid.UUID
    status: Literal["skipped", "relearning"]
    progress: float


class UploadResponse(BaseModel):
    source_id: uuid.UUID
    filename: str
    status: Literal["uploaded", "processing"]
    message: str


class IngestResponse(BaseModel):
    source_id: uuid.UUID
    parser_run_id: uuid.UUID | None = None
    status: str
    processing_status: str | None = None
    parse_quality_status: str | None = None
    page_count: int = 0
    unit_count: int = 0
    knowledge_count: int = 0
    message: str
    quality_status: str | None = None
    availability_status: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    parser_report_summary: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    selected_engine: str | None = None
    attempted_engines: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class IngestStatusResponse(BaseModel):
    source_id: uuid.UUID
    parser_run_id: uuid.UUID | None = None
    processing_status: str
    parse_quality_status: str | None = None
    stage: str
    progress: int
    quality_status: str | None = None
    availability_status: str
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    parser_report_summary: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    selected_engine: str | None = None
    attempted_engines: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    error_message: str | None = None
    can_open_knowledge_base: bool
    next_action: Literal["wait", "review", "upload_text_pdf", "open_knowledge_base"]
    message: str


class DeleteKnowledgeSourceResponse(BaseModel):
    source_id: uuid.UUID
    deleted: bool
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
    episode_id: str | None = None
    episode_trace_url: str | None = None
    verification_status: str | None = None
    runtime_events_count: int | None = None
    verification_report: dict[str, Any] | None = None
    mastery_update: dict[str, Any] | None = None


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


class ParserReviewActionRequest(BaseModel):
    patch: dict[str, Any] | None = None
    review_note: str | None = Field(default=None, max_length=500)
    allow_blocker_ignore: bool = False


def _source_parser_payload(source: KnowledgeSource) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    parser_report = metadata.get("parser_report") or {}
    warnings = parser_report.get("warnings") or []
    if metadata.get("warning") and metadata["warning"] not in warnings:
        warnings = [*warnings, metadata["warning"]]
    return {
        **_source_quality_payload(source),
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


def _source_quality_payload(source: KnowledgeSource) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    quality_score = metadata.get("quality_score") if isinstance(metadata.get("quality_score"), dict) else {}
    quality_status = metadata.get("quality_status")
    if not quality_status and source.status in {"published", "review_required", "partial_indexed", "blocked"}:
        quality_status = source.status
    availability_status = metadata.get("availability_status")
    if not availability_status and quality_status:
        availability_status = availability_status_for_quality(str(quality_status))
    return {
        "latest_parser_run_id": metadata.get("latest_parser_run_id"),
        "parser_status": metadata.get("parser_status"),
        "processing_status": metadata.get("processing_status") or source.status,
        "quality_score": metadata.get("quality_score"),
        "quality_status": quality_status,
        "parse_quality_status": metadata.get("parse_quality_status"),
        "availability_status": availability_status or "unavailable",
        "blocking_reasons": metadata.get("blocking_reasons") or quality_score.get("blocking_reasons") or [],
        "pending_review_count": int(metadata.get("pending_review_count") or 0),
        "pending_blocker_count": int(metadata.get("pending_blocker_count") or 0),
        "review_warning_count": int(metadata.get("review_warning_count") or 0),
        "parser_report_summary": metadata.get("parser_report_summary") or {},
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


def _source_payload(
    source: KnowledgeSource,
    *,
    progress: float = 0.0,
    requires_review: bool | None = None,
) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    return {
        **_source_quality_payload(source),
        "id": str(source.id),
        "title": source.title,
        "filename": source.filename,
        "publisher": source.publisher or "人民教育出版社（PEP）",
        "edition": source.edition or "人教版",
        "grade": source.grade,
        "volume": source.volume,
        "status": source.status,
        "unit_count": source.unit_count,
        "knowledge_count": source.knowledge_count,
        "progress": progress,
        "requires_review": _quality_status_for_source(source) == "review_required"
        if requires_review is None
        else requires_review,
        "page_count": source.page_count,
        "can_delete": source.visibility == "private",
        "subject": metadata.get("subject"),
        "province": metadata.get("province"),
        "city": metadata.get("city"),
        "edition_year": metadata.get("edition_year"),
        "selection_basis_url": metadata.get("selection_basis_url"),
        "official_material_url": metadata.get("official_material_url"),
        "official_material_note": metadata.get("official_material_note"),
    }


def _recalculate_source_quality_gate(source: KnowledgeSource, pending_review_count: int) -> None:
    metadata = dict(source.metadata_ or {})
    report = dict(metadata.get("parser_report") or {})
    if not report:
        report = {
            "unit_count": source.unit_count,
            "expected_unit_count": source.unit_count or None,
            "source_page_coverage_rate": 1.0,
            "evidence_ref_coverage_rate": 1.0,
            "rag_chunk_count": metadata.get("rag_chunk_count", 1),
            "rag_page_coverage_rate": 1.0,
            "requires_review_count": pending_review_count,
        }
    report["requires_review_count"] = pending_review_count
    report.setdefault("pending_blocker_count", 0)
    report.setdefault("review_warning_count", pending_review_count)
    score = score_textbook_quality(report)
    metadata["parser_report"] = report
    metadata.update(quality_summary(score, report))
    source.metadata_ = metadata
    source.status = "completed"


def _review_queue_item_payload(item: ParserReviewItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "source_id": str(item.source_id),
        "parser_run_id": str(item.parser_run_id) if item.parser_run_id else None,
        "target_type": item.target_type,
        "target_id": str(item.target_id) if item.target_id else None,
        "issue_type": item.issue_type,
        "severity": item.severity,
        "evidence_snapshot": item.evidence_snapshot or {},
        "suggested_fix": item.suggested_fix or {},
        "decision": item.decision,
        "review_note": item.review_note,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _source_quality_summary_payload(source: KnowledgeSource) -> dict[str, Any]:
    quality = _source_quality_payload(source)
    score = quality.get("quality_score") if isinstance(quality.get("quality_score"), dict) else {}
    return {
        "source_id": str(source.id),
        "title": source.title,
        "status": source.status,
        "quality_status": quality.get("quality_status"),
        "availability_status": quality.get("availability_status"),
        "overall_score": score.get("overall_score"),
        "parser_status": quality.get("parser_status"),
        "latest_parser_run_id": quality.get("latest_parser_run_id"),
        "pending_review_count": quality.get("pending_review_count"),
        "pending_blocker_count": quality.get("pending_blocker_count"),
        "review_warning_count": quality.get("review_warning_count"),
        "blocking_reasons": quality.get("blocking_reasons"),
        "parser_report_summary": quality.get("parser_report_summary"),
    }


def _recent_failed_source_detail(source: KnowledgeSource | None) -> dict[str, Any] | None:
    if source is None:
        return None
    quality = _source_quality_payload(source)
    return {
        "source_id": str(source.id),
        "title": source.title,
        "filename": source.filename,
        "status": source.status,
        "quality_status": quality.get("quality_status"),
        "can_delete": source.visibility == "private",
        "blocking_reasons": quality.get("blocking_reasons") or [],
        "parser_report_summary": quality.get("parser_report_summary") or {},
    }


def _availability_for_source(source: KnowledgeSource) -> str:
    return str(_source_quality_payload(source).get("availability_status") or "unavailable")


def _quality_status_for_source(source: KnowledgeSource) -> str:
    return str(_source_quality_payload(source).get("quality_status") or "pending")


def _source_can_open(source: KnowledgeSource) -> bool:
    return _availability_for_source(source) in {"available", "partially_available", "needs_review"}


def _ingest_message(status_value: str, blocking_reasons: list[str]) -> str:
    messages = {
        "published": "教材解析完成，知识库已可用。",
        "review_required": "教材解析完成，但需要校对后使用。",
        "partial_indexed": "教材部分解析完成，可先使用部分内容。",
        "blocked": "教材解析完成，但存在阻断问题，请查看解析报告。",
        "failed": "教材解析失败或 PDF 文本层不可用，知识库暂不可用，请查看失败原因。",
    }
    message = messages.get(status_value, f"教材解析完成，当前状态：{status_value}。")
    if status_value == "failed" and _has_scanned_text_layer_reason(blocking_reasons):
        message += " 已尝试本地 OCR；如果仍不可用，请换成已 OCR、可复制文字的 PDF。"
    return message


def _has_scanned_text_layer_reason(blocking_reasons: list[str]) -> bool:
    joined = " ".join(blocking_reasons).casefold()
    return any(token in joined for token in ("scanned", "no usable text layer", "text layer", "ocr"))


def _ingest_response(source: KnowledgeSource, page_count: int) -> IngestResponse:
    quality = _source_quality_payload(source)
    raw_quality_status = quality.get("quality_status")
    quality_status = str(raw_quality_status) if raw_quality_status else None
    availability_status = str(
        quality.get("availability_status")
        or (availability_status_for_quality(quality_status) if quality_status else "unavailable")
    )
    blocking_reasons = list(quality.get("blocking_reasons") or [])
    parser_report_summary = dict(quality.get("parser_report_summary") or {})
    document_quality = dict(
        parser_report_summary.get("document_quality")
        or (source.metadata_ or {}).get("document_quality")
        or {}
    )
    latest_parser_run_id = quality.get("latest_parser_run_id")
    return IngestResponse(
        source_id=source.id,
        parser_run_id=uuid.UUID(str(latest_parser_run_id)) if latest_parser_run_id else None,
        status=source.status,
        processing_status=str(quality.get("processing_status") or source.status),
        parse_quality_status=(
            str(quality.get("parse_quality_status")) if quality.get("parse_quality_status") else None
        ),
        page_count=page_count,
        unit_count=source.unit_count,
        knowledge_count=source.knowledge_count,
        message=_ingest_message(quality_status or source.status, blocking_reasons),
        quality_status=quality_status,
        availability_status=availability_status,
        blocking_reasons=blocking_reasons,
        parser_report_summary=parser_report_summary,
        quality_summary=document_quality,
        selected_engine=(source.metadata_ or {}).get("selected_engine"),
        attempted_engines=list((source.metadata_ or {}).get("attempted_engines") or []),
        fallback_used=bool((source.metadata_ or {}).get("fallback_used", False)),
    )


def _status_message(payload: IngestStatusResponse) -> str:
    if payload.processing_status in {"queued", "running"}:
        return "教材正在后台解析，请稍后查看进度。"
    if payload.processing_status == "failed" or payload.quality_status == "failed":
        return _ingest_message("failed", payload.blocking_reasons)
    if payload.parse_quality_status == "needs_ocr":
        return "当前 PDF 文本层较弱，系统会尝试本地 OCR；如仍不完整，请上传已 OCR 的可搜索 PDF。"
    if payload.next_action == "review":
        return "教材解析完成，但需要校对后使用。"
    if payload.can_open_knowledge_base:
        return "教材解析完成，知识库已可用。"
    return "教材暂不可用，请查看失败原因。"


def _ingest_status_payload(source: KnowledgeSource, parser_run: ParserRun | None) -> IngestStatusResponse:
    quality = _source_quality_payload(source)
    quality_status = str(quality.get("quality_status") or "pending")
    availability_status = str(quality.get("availability_status") or "unavailable")
    parser_report_summary = dict(quality.get("parser_report_summary") or {})
    metadata = source.metadata_ or {}
    quality_summary_payload = dict(
        parser_report_summary.get("document_quality")
        or metadata.get("document_quality")
        or {}
    )
    report = parser_run.quality_report if parser_run and isinstance(parser_run.quality_report, dict) else {}
    warnings = list(parser_report_summary.get("warnings") or report.get("warnings") or [])
    blocking_reasons = list(quality.get("blocking_reasons") or [])
    processing_status = parser_run.status if parser_run else str(quality.get("processing_status") or source.status)
    stage = parser_run.stage if parser_run else str(metadata.get("parser_stage") or processing_status)
    progress = int(parser_run.progress if parser_run else metadata.get("parser_progress") or 0)
    can_open = availability_status in {"available", "partially_available", "needs_review"}
    parse_quality_status = (
        str(quality.get("parse_quality_status")) if quality.get("parse_quality_status") else None
    )
    next_action: Literal["wait", "review", "upload_text_pdf", "open_knowledge_base"]
    if processing_status in {"queued", "running"}:
        next_action = "wait"
    elif quality_status == "failed" or _has_scanned_text_layer_reason(blocking_reasons):
        next_action = "upload_text_pdf"
    elif availability_status == "needs_review":
        next_action = "review"
    elif can_open:
        next_action = "open_knowledge_base"
    else:
        next_action = "upload_text_pdf"
    payload = IngestStatusResponse(
        source_id=source.id,
        parser_run_id=parser_run.id if parser_run else None,
        processing_status=processing_status,
        parse_quality_status=parse_quality_status,
        stage=stage,
        progress=progress,
        quality_status=quality_status,
        availability_status=availability_status,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        parser_report_summary=parser_report_summary,
        quality_summary=quality_summary_payload,
        selected_engine=metadata.get("selected_engine") or report.get("selected_engine"),
        attempted_engines=list(metadata.get("attempted_engines") or report.get("attempted_engines") or []),
        fallback_used=bool(metadata.get("fallback_used", report.get("fallback_used", False))),
        error_message=parser_run.error_message if parser_run else metadata.get("error"),
        can_open_knowledge_base=can_open,
        next_action=next_action,
        message="",
    )
    payload.message = _status_message(payload)
    return payload


def _ensure_source_review_access(source: KnowledgeSource, learner_id: uuid.UUID) -> None:
    if source.owner_learner_id not in (None, learner_id) and source.visibility != "public":
        raise HTTPException(status_code=403, detail="无权查看该教材审核队列")


async def _load_review_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    learner_id: uuid.UUID,
) -> KnowledgeSource:
    await _ensure_learner(db, learner_id)
    source_result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = source_result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    _ensure_source_review_access(source, learner_id)
    return source


async def _load_review_item(
    db: AsyncSession,
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
) -> ParserReviewItem:
    result = await db.execute(
        select(ParserReviewItem).where(
            ParserReviewItem.id == review_item_id,
            ParserReviewItem.source_id == source_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


async def _load_review_target(db: AsyncSession, item: ParserReviewItem) -> Any | None:
    if item.target_id is None:
        return None
    model_by_type = {
        "knowledge_point": KnowledgePoint,
        "exercise_question": ExerciseQuestion,
        "knowledge_chunk": KnowledgeChunk,
        "curriculum_node": CurriculumNode,
    }
    model = model_by_type.get(item.target_type)
    if model is None:
        return None
    result = await db.execute(select(model).where(model.id == item.target_id))
    return result.scalar_one_or_none()


def _apply_review_patch(target: Any | None, patch: dict[str, Any] | None) -> None:
    if target is None or not patch:
        return
    if isinstance(target, KnowledgePoint):
        _apply_allowed_attrs(target, patch, {"title", "summary", "source_page", "difficulty"})
        content_patch = patch.get("content")
        if isinstance(content_patch, dict):
            content = dict(target.content or {})
            for key in {
                "text",
                "source_page",
                "confidence",
                "warnings",
                "raw_line",
                "evidence_refs",
                "evidence_pdf_pages",
                "lemma",
                "origin",
            }:
                if key in content_patch:
                    content[key] = content_patch[key]
            if "source_page" in content_patch:
                target.source_page = str(content_patch["source_page"])
            target.content = content
    elif isinstance(target, ExerciseQuestion):
        _apply_allowed_attrs(
            target,
            patch,
            {"stem", "options", "answer", "explanation", "difficulty"},
        )
        metadata_patch = patch.get("metadata") or patch.get("content")
        if isinstance(metadata_patch, dict):
            metadata = dict(target.metadata_ or {})
            for key in {"source_page", "confidence", "warnings", "evidence_refs", "parser_run_id"}:
                if key in metadata_patch:
                    metadata[key] = metadata_patch[key]
            target.metadata_ = metadata
    elif isinstance(target, KnowledgeChunk):
        _apply_allowed_attrs(target, patch, {"content", "page_number"})
        metadata_patch = patch.get("metadata") or patch.get("content")
        if isinstance(metadata_patch, dict):
            metadata = dict(target.metadata_ or {})
            for key in {"source_page", "confidence", "warnings", "parser_run_id", "origin"}:
                if key in metadata_patch:
                    metadata[key] = metadata_patch[key]
            target.metadata_ = metadata
    elif isinstance(target, CurriculumNode):
        _apply_allowed_attrs(
            target,
            patch,
            {"title", "subtitle", "start_page", "end_page", "learning_objectives"},
        )


def _apply_allowed_attrs(target: Any, patch: dict[str, Any], allowed: set[str]) -> None:
    for key in allowed:
        if key not in patch:
            continue
        setattr(target, key, patch[key])


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
    return and_(
        KnowledgePoint.source_id == node.source_id,
        or_(
            KnowledgePoint.curriculum_node_id == node.id,
            and_(
                KnowledgePoint.type == "grammar",
                KnowledgePoint.content["related_units"].contains([node.title]),
            ),
        ),
    )


def _unit_point_order():
    return (
        case((KnowledgePoint.type == "vocabulary", 0), else_=1),
        KnowledgePoint.content["unit_order"].as_integer().asc().nullslast(),
        KnowledgePoint.created_at.asc(),
    )


def _knowledge_point_summary_payload(
    point: KnowledgePoint,
    states: dict[uuid.UUID, LearnerKnowledgeState],
) -> dict[str, Any]:
    content = point.content or {}
    return {
        "id": str(point.id),
        "title": point.title,
        "type": point.type,
        "summary": point.summary,
        "source_page": point.source_page,
        "unit_order": content.get("unit_order"),
        "requires_review": bool(content.get("requires_review", False)),
        "warnings": content.get("warnings", []),
        "confidence": content.get("confidence"),
        "raw_line": content.get("raw_line"),
        "evidence": [
            f"来源页码：{point.source_page}",
            f"解析器：{content.get('origin', 'unknown')}",
        ],
        "mastery": states.get(point.id).mastery_score if point.id in states else 0.0,
    }


def _workspace_item_payload(
    point: KnowledgePoint,
    states: dict[uuid.UUID, LearnerKnowledgeState],
) -> dict[str, Any]:
    content = point.content or {}
    return {
        "id": str(point.id),
        "title": point.title,
        "summary": point.summary,
        "source_page": point.source_page,
        "mastery": states.get(point.id).mastery_score if point.id in states else 0.0,
        "unit_order": content.get("unit_order"),
        "meta": {
            key: value
            for key, value in {
                "phonetic": content.get("phonetic"),
                "part_of_speech": content.get("part_of_speech"),
                "chinese_meaning": content.get("chinese_meaning"),
                "theme": content.get("theme"),
            }.items()
            if value
        },
    }


def _workspace_section_action(section_id: str) -> dict[str, Any]:
    actions = {
        "vocabulary": {"type": "vocabulary_new", "label": "认识新词"},
        "sentence_patterns": {"type": "daily_lesson", "label": "用 AI 每日题练句式"},
        "grammar": {"type": "grammar", "label": "进入语法学习"},
        "phrases": {"type": "daily_lesson", "label": "放进今日任务"},
        "pronunciation": {"type": "pronunciation", "label": "练发音"},
        "practice": {"type": "exercise", "label": "开始教材练习"},
    }
    return actions[section_id]


def _build_unit_workspace(
    *,
    source: KnowledgeSource,
    node: CurriculumNode,
    points: list[KnowledgePoint],
    review_points: list[KnowledgePoint],
    states: dict[uuid.UUID, LearnerKnowledgeState],
    recommendation_reason: str,
) -> dict[str, Any]:
    by_type: dict[str, list[KnowledgePoint]] = {
        "vocabulary": [],
        "sentence_pattern": [],
        "grammar": [],
        "phrase": [],
        "pronunciation": [],
        "text_note": [],
    }
    for point in points:
        by_type.setdefault(point.type, []).append(point)

    overview_point = next(
        (
            point
            for point in by_type.get("text_note", [])
            if (point.content or {}).get("role") == "unit_overview"
        ),
        None,
    )
    sections_config = [
        ("vocabulary", "核心词汇", "vocabulary"),
        ("sentence_patterns", "句式", "sentence_pattern"),
        ("grammar", "语法", "grammar"),
        ("phrases", "短语", "phrase"),
        ("pronunciation", "语音", "pronunciation"),
    ]
    sections = []
    for section_id, title, point_type in sections_config:
        section_points = by_type.get(point_type, [])
        visible_points = section_points if section_id == "vocabulary" else section_points[:8]
        sections.append(
            {
                "id": section_id,
                "title": title,
                "count": len(section_points),
                "items": [_workspace_item_payload(point, states) for point in visible_points],
                "action": _workspace_section_action(section_id),
                "empty": len(section_points) == 0,
            }
        )

    mastery_values = [
        states.get(point.id).mastery_score if point.id in states else 0.0
        for point in points
        if point.type != "text_note"
    ]
    mastered_count = sum(1 for value in mastery_values if value >= 0.8)
    learning_count = sum(1 for value in mastery_values if 0 < value < 0.8)
    new_count = sum(1 for value in mastery_values if value == 0)
    average_mastery = sum(mastery_values) / len(mastery_values) if mastery_values else 0.0

    if review_points:
        recommended = {
            "type": "review",
            "label": "先校对低置信条目",
            "reason": "当前单元有待校对条目，确认后再进入正式练习更稳。",
        }
    elif by_type.get("vocabulary") and new_count:
        recommended = {
            "type": "vocabulary_new",
            "label": "先认识本单元新词",
            "reason": recommendation_reason,
        }
    elif by_type.get("grammar"):
        recommended = {
            "type": "grammar",
            "label": f"学习语法：{by_type['grammar'][0].title}",
            "target": by_type["grammar"][0].title,
            "reason": recommendation_reason,
        }
    else:
        recommended = {
            "type": "exercise",
            "label": "开始教材练习",
            "reason": recommendation_reason,
        }

    return {
        "unit": {
            "id": str(node.id),
            "title": node.title,
            "subtitle": node.subtitle or "",
            "estimated_minutes": node.estimated_minutes or 20,
            "source_id": str(source.id),
            "source_title": source.title,
        },
        "overview": {
            "title": overview_point.title if overview_point else f"{node.title} overview",
            "summary": overview_point.summary
            if overview_point
            else f"{node.title} {node.subtitle or ''}".strip(),
            "objectives": node.learning_objectives or [],
        },
        "sections": sections
        + [
            {
                "id": "practice",
                "title": "练习",
                "count": len(points),
                "items": [],
                "action": _workspace_section_action("practice"),
                "empty": False,
            }
        ],
        "mastery_summary": {
            "average": round(average_mastery, 4),
            "mastered_count": mastered_count,
            "learning_count": learning_count,
            "new_count": new_count,
            "total_count": len(mastery_values),
        },
        "recommended_next_action": recommended,
    }


async def _backfill_vocabulary_states_from_items(
    db: AsyncSession,
    learner_id: uuid.UUID,
    points: list[KnowledgePoint],
    states: dict[uuid.UUID, LearnerKnowledgeState],
) -> None:
    vocabulary_point_ids = [point.id for point in points if point.type == "vocabulary"]
    missing_point_ids = [point_id for point_id in vocabulary_point_ids if point_id not in states]
    if not missing_point_ids:
        return
    rows_result = await db.execute(
        select(VocabularyItem, VocabularyItemSource)
        .join(VocabularyItemSource, VocabularyItemSource.vocabulary_item_id == VocabularyItem.id)
        .where(
            VocabularyItem.learner_id == learner_id,
            VocabularyItemSource.learner_id == learner_id,
            VocabularyItemSource.source_type == "textbook_unit",
            VocabularyItemSource.source_id.in_([str(point_id) for point_id in missing_point_ids]),
            VocabularyItemSource.active.is_(True),
            VocabularyItem.review_count > 0,
        )
    )
    now = datetime.now(timezone.utc)
    for item, source in rows_result.all():
        try:
            point_id = uuid.UUID(str(source.source_id))
        except (TypeError, ValueError):
            continue
        if point_id in states:
            continue
        mastery = round(max(0.0, min(1.0, float(item.confidence or 0.0))), 4)
        state = LearnerKnowledgeState(
            learner_id=learner_id,
            knowledge_point_id=point_id,
            status="mastered" if mastery >= 0.8 or item.status == "mastered" else "learning",
            mastery_score=mastery,
            confidence=mastery,
            exposure_count=item.review_count or 1,
            correct_count=1 if mastery > 0 else 0,
            last_seen_at=item.last_reviewed_at or now,
            next_review_at=item.next_review_at,
            evidence_summary={
                "source": "vocabulary_practice_backfill",
                "vocabulary_item_id": str(item.id),
                "word": item.word,
                "review_count": item.review_count,
                "item_status": item.status,
            },
        )
        db.add(state)
        states[point_id] = state
    if states:
        await db.flush()


@router.get("/api/learners/{learner_id}/knowledge-base")
async def knowledge_base_overview(
    learner_id: uuid.UUID,
    source_id: uuid.UUID | None = Query(default=None),
    node_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner(db, learner_id)
    available_status_filter = or_(
        KnowledgeSource.metadata_["availability_status"].as_string().in_(
            ["available", "partially_available", "needs_review"]
        ),
        KnowledgeSource.status.in_(["published", "review_required", "partial_indexed"]),
    )
    source_filter = and_(
        available_status_filter,
        or_(
            KnowledgeSource.owner_learner_id == learner_id,
            KnowledgeSource.visibility == "public",
        ),
    )
    source_list_result = await db.execute(
        select(KnowledgeSource)
        .where(source_filter)
        .order_by(KnowledgeSource.created_at.desc().nullslast(), KnowledgeSource.title.asc())
    )
    available_sources = list(source_list_result.scalars().all())
    if source_id is not None:
        source = next((item for item in available_sources if item.id == source_id), None)
        if source is None:
            raise HTTPException(status_code=404, detail="Knowledge source not found")
    else:
        source = available_sources[0] if available_sources else None
    if source is None:
        failed_result = await db.execute(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.status == "failed",
                or_(
                    KnowledgeSource.owner_learner_id == learner_id,
                    KnowledgeSource.visibility == "public",
                ),
            )
            .order_by(KnowledgeSource.created_at.desc().nullslast(), KnowledgeSource.title.asc())
            .limit(1)
        )
        failed_source = failed_result.scalar_one_or_none()
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Published textbook not found",
                "failed_source": _recent_failed_source_detail(failed_source),
            },
        )

    source_result = await db.execute(
        select(KnowledgeSource)
        .where(
            KnowledgeSource.id == source.id,
        )
        .limit(1)
    )
    source = source_result.scalar_one_or_none() or source

    node_result = await db.execute(
        select(CurriculumNode)
        .where(CurriculumNode.source_id == source.id, CurriculumNode.parent_id.is_(None))
        .order_by(CurriculumNode.ordinal.asc())
    )
    nodes = list(node_result.scalars().all())
    if not nodes:
        raise HTTPException(status_code=409, detail="Textbook curriculum has not been generated")
    node_ids = [node.id for node in nodes]
    point_statuses = learnable_point_statuses(source)
    mastery_result = await db.execute(
        select(
            CurriculumNode.id.label("curriculum_node_id"),
            func.count(KnowledgePoint.id).label("point_count"),
            func.avg(func.coalesce(LearnerKnowledgeState.mastery_score, 0.0)).label("average_mastery"),
            func.max(
                LearningProgressItem.metadata_["progress_override"].as_float()
            ).label("progress_override"),
            func.max(
                LearningProgressItem.metadata_["progress_mode"].as_string()
            ).label("progress_mode"),
        )
        .select_from(CurriculumNode)
        .outerjoin(
            KnowledgePoint,
            and_(
                KnowledgePoint.curriculum_node_id == CurriculumNode.id,
                KnowledgePoint.source_id == source.id,
                KnowledgePoint.status.in_(point_statuses),
                KnowledgePoint.type != "text_note",
            ),
        )
        .outerjoin(
            LearnerKnowledgeState,
            and_(
                LearnerKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                LearnerKnowledgeState.learner_id == learner_id,
            ),
        )
        .outerjoin(
            LearningProgressItem,
            and_(
                LearningProgressItem.learner_id == learner_id,
                LearningProgressItem.skill == "knowledge_unit",
                LearningProgressItem.item_id == cast(CurriculumNode.id, String),
            ),
        )
        .where(
            CurriculumNode.id.in_(node_ids),
        )
        .group_by(CurriculumNode.id)
    )
    unit_progress_overrides: dict[uuid.UUID, float] = {}
    unit_progress_modes: dict[uuid.UUID, str] = {}
    completed_node_ids: set[uuid.UUID] = set()
    for row in mastery_result:
        progress_mode = getattr(row, "progress_mode", None)
        progress_override = getattr(row, "progress_override", None)
        if progress_mode in {"skipped", "relearning"} and progress_override is not None:
            normalized_override = max(0.0, min(1.0, float(progress_override)))
            unit_progress_overrides[row.curriculum_node_id] = normalized_override
            unit_progress_modes[row.curriculum_node_id] = progress_mode
            if normalized_override >= 1.0:
                completed_node_ids.add(row.curriculum_node_id)
            continue
        if int(row.point_count or 0) > 0 and float(row.average_mastery or 0.0) >= 0.8:
            completed_node_ids.add(row.curriculum_node_id)

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
            KnowledgePoint.status.in_(point_statuses),
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
        await _backfill_vocabulary_states_from_items(db, learner_id, points, states)

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

    recommendation_reason = MemoryExplainer().recommendation_reason(
        memory_items,
        f"已根据教材顺序和完成记录，为你推荐 {recommended_node.title}。",
    )

    return {
        "source": _source_payload(
            source,
            progress=progress,
            requires_review=_quality_status_for_source(source) == "review_required" or bool(review_points),
        ),
        "sources": [
            _source_payload(item, requires_review=_quality_status_for_source(item) == "review_required")
            for item in available_sources
        ],
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
                "progress_override": unit_progress_overrides.get(node.id),
                "progress_mode": unit_progress_modes.get(node.id),
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
            "progress_override": unit_progress_overrides.get(display_node.id),
            "progress_mode": unit_progress_modes.get(display_node.id),
        },
        "daily_lesson": {
            "id": f"lesson-{display_node.id}",
            "title": f"{display_node.title} {display_node.subtitle or ''}".strip(),
            "estimated_minutes": display_node.estimated_minutes or 20,
            "parts": _lesson_parts(points),
        },
        "knowledge_points": [
            _knowledge_point_summary_payload(point, states)
            for point in points
        ],
        "unit_workspace": _build_unit_workspace(
            source=source,
            node=display_node,
            points=points,
            review_points=review_points,
            states=states,
            recommendation_reason=recommendation_reason,
        ),
        "review": {
            "requires_review": _quality_status_for_source(source) == "review_required" or bool(review_points),
            "pending_count": len(review_points),
            "low_confidence_count": sum(
                1 for point in review_points if ((point.content or {}).get("confidence") or 1) < 0.75
            ),
            "warning_count": sum(1 for point in review_points if (point.content or {}).get("warnings")),
            "items": [_review_item_payload(point) for point in review_points],
        },
        "parser_evidence": _source_parser_payload(source),
        "path": path,
        "recommendation_reason": recommendation_reason,
    }


@router.put(
    "/api/learners/{learner_id}/knowledge-base/units/{curriculum_node_id}/progress",
    response_model=UnitProgressResponse,
)
async def update_unit_progress(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    body: UpdateUnitProgressRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UnitProgressResponse:
    await _ensure_learner(db, learner_id)
    node_result = await db.execute(
        select(CurriculumNode)
        .join(KnowledgeSource, KnowledgeSource.id == CurriculumNode.source_id)
        .where(
            CurriculumNode.id == curriculum_node_id,
            CurriculumNode.node_type == "unit",
            or_(
                KnowledgeSource.owner_learner_id == learner_id,
                KnowledgeSource.visibility == "public",
            ),
        )
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum unit not found")

    progress_result = await db.execute(
        select(LearningProgressItem).where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "knowledge_unit",
            LearningProgressItem.item_id == str(curriculum_node_id),
        )
    )
    item = progress_result.scalar_one_or_none()
    if item is None:
        item = LearningProgressItem(
            learner_id=learner_id,
            skill="knowledge_unit",
            item_id=str(curriculum_node_id),
            title=node.title,
            status="opened",
            is_favorite=False,
            opened_count=0,
            metadata_={},
        )
        db.add(item)

    now = datetime.now(timezone.utc)
    item.title = node.title
    if body.action == "skip":
        item.status = "learned"
        item.learned_at = now
        item.metadata_ = {
            "progress_mode": "skipped",
            "progress_override": 1.0,
            "source_id": str(node.source_id),
        }
        response_status = "skipped"
        progress = 1.0
    else:
        item.status = "opened"
        item.learned_at = None
        item.opened_count = (item.opened_count or 0) + 1
        item.last_opened_at = now
        item.metadata_ = {
            "progress_mode": "relearning",
            "progress_override": 0.0,
            "source_id": str(node.source_id),
        }
        response_status = "relearning"
        progress = 0.0

    await db.flush()
    return UnitProgressResponse(
        curriculum_node_id=curriculum_node_id,
        status=response_status,
        progress=progress,
    )


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
    remaining_count = int(remaining_result.scalar_one() or 0)
    source_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == point.source_id)
    )
    source = source_result.scalar_one_or_none()
    if source is not None:
        review_items_result = await db.execute(
            select(ParserReviewItem).where(
                ParserReviewItem.source_id == point.source_id,
                ParserReviewItem.target_type == "knowledge_point",
                ParserReviewItem.target_id == point.id,
                ParserReviewItem.decision == "pending",
            )
        )
        pending_review_items = list(review_items_result.scalars().all())
        for item in pending_review_items:
            item.decision = content["review_decision"]
            item.review_note = body.note
            item.reviewed_by_learner_id = learner_id
            item.reviewed_at = datetime.now(timezone.utc)
        if pending_review_items:
            await recalculate_quality_gate_from_queue(db, source)
        else:
            _recalculate_source_quality_gate(source, remaining_count)
    return KnowledgeReviewResponse(
        knowledge_point_id=point.id,
        action=body.action,
        status=point.status,
        requires_review=bool(content.get("requires_review", False)),
    )


@router.get("/api/knowledge/sources/{source_id}/review-items")
async def list_parser_review_items(
    source_id: uuid.UUID,
    learner_id: uuid.UUID = Query(),
    decision: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    parser_run_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_review_source(db, source_id, learner_id)
    filters = [ParserReviewItem.source_id == source_id]
    if decision:
        filters.append(ParserReviewItem.decision == decision)
    if severity:
        filters.append(ParserReviewItem.severity == severity)
    if issue_type:
        filters.append(ParserReviewItem.issue_type == issue_type)
    if target_type:
        filters.append(ParserReviewItem.target_type == target_type)
    if parser_run_id is not None:
        filters.append(ParserReviewItem.parser_run_id == parser_run_id)
    result = await db.execute(
        select(ParserReviewItem)
        .where(*filters)
        .order_by(
            ParserReviewItem.severity.asc(),
            ParserReviewItem.created_at.asc().nullslast(),
        )
    )
    items = list(result.scalars().all())
    all_result = await db.execute(select(ParserReviewItem).where(ParserReviewItem.source_id == source_id))
    summary = queue_summary(list(all_result.scalars().all()))
    apply_quality_gate(source, summary=summary)
    return {
        "source": _source_payload(source),
        "source_quality_summary": _source_quality_summary_payload(source),
        "summary": {
            "pending_review_count": summary.pending_review_count,
            "pending_blocker_count": summary.pending_blocker_count,
            "review_warning_count": summary.review_warning_count,
        },
        "items": [_review_queue_item_payload(item) for item in items],
    }


@router.get("/api/knowledge/sources/{source_id}/review-items/{review_item_id}")
async def get_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_review_source(db, source_id, learner_id)
    item = await _load_review_item(db, source_id, review_item_id)
    return {
        "source": _source_payload(source),
        "source_quality_summary": _source_quality_summary_payload(source),
        "item": _review_queue_item_payload(item),
    }


@router.post("/api/knowledge/sources/{source_id}/review-items/{review_item_id}/confirm")
async def confirm_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: ParserReviewActionRequest | None = None,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_parser_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        learner_id=learner_id,
        action="confirmed",
        body=body or ParserReviewActionRequest(),
        db=db,
    )


@router.post("/api/knowledge/sources/{source_id}/review-items/{review_item_id}/update")
async def update_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: ParserReviewActionRequest,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_parser_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        learner_id=learner_id,
        action="updated",
        body=body,
        db=db,
    )


@router.post("/api/knowledge/sources/{source_id}/review-items/{review_item_id}/ignore")
async def ignore_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: ParserReviewActionRequest | None = None,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_parser_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        learner_id=learner_id,
        action="ignored",
        body=body or ParserReviewActionRequest(),
        db=db,
    )


async def _decide_parser_review_item(
    *,
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    learner_id: uuid.UUID,
    action: str,
    body: ParserReviewActionRequest,
    db: AsyncSession,
) -> dict[str, Any]:
    source = await _load_review_source(db, source_id, learner_id)
    item = await _load_review_item(db, source_id, review_item_id)
    if item.decision != "pending":
        raise HTTPException(status_code=409, detail="Review item has already been decided")
    if action == "ignored" and item.severity == "blocker" and not body.allow_blocker_ignore:
        raise HTTPException(
            status_code=409,
            detail="Blocker review item requires allow_blocker_ignore=true and review_note.",
        )
    if action == "ignored" and item.severity == "blocker" and not body.review_note:
        raise HTTPException(status_code=422, detail="Ignoring a blocker requires review_note")

    target = await _load_review_target(db, item)
    if action == "updated":
        _apply_review_patch(target, body.patch)
    if action in {"confirmed", "updated"} or item.severity in {"warning", "info"} or body.allow_blocker_ignore:
        mark_target_reviewed(
            target,
            decision=action,
            learner_id=learner_id,
            note=body.review_note,
        )
    item.decision = action
    item.review_note = body.review_note
    item.reviewed_by_learner_id = learner_id
    item.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    summary = await recalculate_quality_gate_from_queue(db, source)
    return {
        "source": _source_payload(source),
        "source_quality_summary": _source_quality_summary_payload(source),
        "summary": {
            "pending_review_count": summary.pending_review_count,
            "pending_blocker_count": summary.pending_blocker_count,
            "review_warning_count": summary.review_warning_count,
        },
        "item": _review_queue_item_payload(item),
    }


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
        .where(_unit_point_filter(node))
        .order_by(*_unit_point_order())
    )
    source_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == node.source_id)
    )
    source = source_result.scalar_one()
    points = [
        point
        for point in point_result.scalars().all()
        if point.status in learnable_point_statuses(source)
    ]
    lesson_parts = _lesson_parts(points)
    enrollment = await enroll_unit_vocabulary(db, learner_id, node, source=source)

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
            vocab = VocabularyItem(
                learner_id=learner_id,
                word=point.title,
                canonical_key=canonical_vocabulary_key(point.title),
                entry_kind=(point.content or {}).get("entry_kind") or "word",
                preferred_accent="auto",
                level=(point.content or {}).get("grade") or "unknown",
                meanings=[point.summary],
                source_ref=f"knowledge:{point.id}",
                status="learning",
                confidence=mastery,
                next_review_at=learner_state.next_review_at,
            )
            db.add(vocab)
            await db.flush()
        else:
            vocab.confidence = mastery
            vocab.next_review_at = learner_state.next_review_at
        if is_unit_wordlist_point(point) and point.curriculum_node_id:
            source_result = await db.execute(
                select(VocabularyItemSource.id).where(
                    VocabularyItemSource.learner_id == learner_id,
                    VocabularyItemSource.vocabulary_item_id == vocab.id,
                    VocabularyItemSource.source_type == "textbook_unit",
                    VocabularyItemSource.source_id == str(point.id),
                    VocabularyItemSource.active.is_(True),
                )
            )
            if source_result.scalar_one_or_none() is None:
                db.add(
                    VocabularyItemSource(
                        learner_id=learner_id,
                        vocabulary_item_id=vocab.id,
                        source_type="textbook_unit",
                        source_id=str(point.id),
                        source_version_id=str(point.source_id),
                        reason="knowledge_point_practiced",
                        priority=0.8,
                        curriculum_node_id=point.curriculum_node_id,
                        display_label="教材单元",
                        context_snapshot={
                            "source_page": point.source_page,
                            "unit_order": (point.content or {}).get("unit_order"),
                            "origin": (point.content or {}).get("origin"),
                        },
                        active=True,
                    )
                )

    await db.flush()
    return KnowledgeAttemptResponse(
        knowledge_point_id=point.id,
        status=learner_state.status,
        mastery_score=mastery,
        exposure_count=learner_state.exposure_count,
        next_review_at=learner_state.next_review_at,
    )


def _infer_grade(filename: str) -> str:
    normalized = filename.casefold().replace("_", "-")
    grade_tokens = (
        ("grade-7", ("七年级", "7年级", "七上", "七下", "grade-7", "grade7")),
        ("grade-8", ("八年级", "8年级", "八上", "八下", "grade-8", "grade8")),
        ("grade-9", ("九年级", "9年级", "九上", "九下", "grade-9", "grade9")),
    )
    for grade, tokens in grade_tokens:
        if any(token in normalized for token in tokens):
            return grade
    return "unknown"


def _infer_volume(filename: str) -> str | None:
    normalized = filename.casefold()
    if any(token in normalized for token in ("下册", "七下", "八下", "九下", "lower")):
        return "lower"
    if any(token in normalized for token in ("上册", "七上", "八上", "九上", "upper")):
        return "upper"
    return None


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
        grade=_infer_grade(safe_filename),
        volume=_infer_volume(safe_filename),
        status="uploaded",
        visibility="private",
        object_key=str(destination),
        sha256=digest,
        file_size=len(data),
        unit_count=0,
        knowledge_count=0,
        metadata_={
            "stage": "uploaded",
            "processing_status": "uploaded",
            "parse_quality_status": "pending",
            "availability_status": "unavailable",
        },
    )
    db.add(source)
    await db.flush()
    return UploadResponse(
        source_id=source.id,
        filename=source.filename,
        status="uploaded",
        message="教材上传成功，已进入知识生成流程。",
    )


@router.delete(
    "/api/knowledge/sources/{source_id}",
    response_model=DeleteKnowledgeSourceResponse,
)
async def delete_knowledge_source(
    source_id: uuid.UUID,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> DeleteKnowledgeSourceResponse:
    await _ensure_learner(db, learner_id)
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    if source.owner_learner_id != learner_id or source.visibility != "private":
        raise HTTPException(status_code=403, detail="只能删除自己上传的私有教材")
    active_run = await _active_parser_run(db, source.id)
    if active_run is not None:
        raise HTTPException(status_code=409, detail="教材正在解析中，请等待解析结束后再删除")

    object_key = source.object_key
    ocr_object_key = (source.metadata_ or {}).get("ocr_object_key")
    should_delete_file = False
    if object_key:
        reference_result = await db.execute(
            select(func.count())
            .select_from(KnowledgeSource)
            .where(KnowledgeSource.object_key == object_key, KnowledgeSource.id != source.id)
        )
        should_delete_file = int(reference_result.scalar_one() or 0) == 0

    await db.delete(source)
    await db.flush()
    if should_delete_file:
        _delete_uploaded_file(object_key)
    if isinstance(ocr_object_key, str) and ocr_object_key != object_key:
        _delete_uploaded_file(ocr_object_key)
    return DeleteKnowledgeSourceResponse(
        source_id=source_id,
        deleted=True,
        message="教材已删除，可以重新上传。",
    )


async def _latest_parser_run(db: AsyncSession, source_id: uuid.UUID) -> ParserRun | None:
    result = await db.execute(
        select(ParserRun)
        .where(ParserRun.source_id == source_id)
        .order_by(ParserRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _delete_uploaded_file(object_key: str) -> None:
    try:
        path = Path(object_key).expanduser().resolve()
        upload_dir = Path(settings.knowledge_upload_dir).expanduser().resolve()
        if path.exists() and path.is_file() and _is_relative_to(path, upload_dir):
            path.unlink()
    except OSError:
        return


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


async def _active_parser_run(db: AsyncSession, source_id: uuid.UUID) -> ParserRun | None:
    result = await db.execute(
        select(ParserRun)
        .where(ParserRun.source_id == source_id, ParserRun.status.in_(["queued", "running"]))
        .order_by(ParserRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _create_queued_parser_run(db: AsyncSession, source: KnowledgeSource) -> ParserRun:
    parser_run = ParserRun(
        source_id=source.id,
        parser_id="document-parser-router",
        parser_version="v1",
        parser_profile_id=None,
        book_manifest_id=None,
        pdf_sha256=source.sha256,
        input_hash=source.sha256,
        status="queued",
        stage="queued",
        progress=0,
        started_at=datetime.now(timezone.utc),
        artifact_refs={},
    )
    db.add(parser_run)
    await db.flush()
    metadata = _clear_stale_ingest_metadata(source.metadata_ or {})
    metadata.update(
        {
            "latest_parser_run_id": str(parser_run.id),
            "processing_status": "queued",
            "parser_status": "queued",
            "parser_stage": "queued",
            "parser_progress": 0,
            "availability_status": metadata.get("availability_status") or "unavailable",
            "parse_quality_status": metadata.get("parse_quality_status") or "pending",
        }
    )
    source.metadata_ = metadata
    source.status = "queued"
    await db.flush()
    return parser_run


def _schedule_ingest_background_task(
    background_tasks: BackgroundTasks,
    *,
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID,
) -> None:
    background_tasks.add_task(_run_ingest_background, source_id, parser_run_id)


async def _run_ingest_background(source_id: uuid.UUID, parser_run_id: uuid.UUID) -> None:
    async with async_session_factory() as db:
        try:
            result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
            source = result.scalar_one_or_none()
            if source is None:
                return
            await process_uploaded_textbook(db, source, parser_run_id=parser_run_id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            async with async_session_factory() as failure_db:
                result = await failure_db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
                source = result.scalar_one_or_none()
                run_result = await failure_db.execute(select(ParserRun).where(ParserRun.id == parser_run_id))
                parser_run = run_result.scalar_one_or_none()
                if parser_run is not None:
                    parser_run.status = "failed"
                    parser_run.stage = "failed"
                    parser_run.progress = max(parser_run.progress or 0, 1)
                    parser_run.error_message = str(exc)[:500]
                    parser_run.completed_at = datetime.now(timezone.utc)
                if source is not None:
                    metadata = dict(source.metadata_ or {})
                    failed_report = {
                        "unit_count": 0,
                        "warnings": [str(exc)[:500]],
                    }
                    failed_score = score_textbook_quality(failed_report, parser_failed=True)
                    metadata.update(
                        {
                            "stage": "failed",
                            "latest_parser_run_id": str(parser_run_id),
                            "processing_status": "failed",
                            "parse_quality_status": "failed",
                            "parser_status": "failed",
                            "parser_stage": "failed",
                            "parser_progress": parser_run.progress if parser_run else 1,
                            "error": str(exc)[:500],
                            "parser_report": failed_report,
                            **quality_summary(failed_score, failed_report),
                        }
                    )
                    source.status = "failed"
                    source.metadata_ = metadata
                await failure_db.commit()


@router.post(
    "/api/knowledge/sources/{source_id}/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_knowledge_source(
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
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
    active_run = await _active_parser_run(db, source.id)
    parser_run = active_run or await _create_queued_parser_run(db, source)
    if active_run is None:
        await db.commit()
        _schedule_ingest_background_task(
            background_tasks,
            source_id=source.id,
            parser_run_id=parser_run.id,
        )
    response = _ingest_response(source, source.page_count or 0)
    response.parser_run_id = parser_run.id
    response.processing_status = parser_run.status
    response.message = "教材已进入后台解析，请稍后查看进度。"
    return response


@router.get(
    "/api/knowledge/sources/{source_id}/ingest-status",
    response_model=IngestStatusResponse,
)
async def get_ingest_status(
    source_id: uuid.UUID,
    learner_id: uuid.UUID = Query(),
    db: AsyncSession = Depends(get_db_session),
) -> IngestStatusResponse:
    await _ensure_learner(db, learner_id)
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="教材不存在")
    if source.owner_learner_id not in (None, learner_id):
        raise HTTPException(status_code=403, detail="无权查看该教材")
    parser_run = await _latest_parser_run(db, source.id)
    return _ingest_status_payload(source, parser_run)


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
    response: Response,
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
    pool = await get_exercise_pool(
        db,
        source_id=node.source_id,
        curriculum_node_id=node.id,
        learner_id=learner_id,
    )
    selected_questions = await select_unit_exercises_for_learner(
        db,
        learner_id=learner_id,
        questions=pool.questions,
        limit=limit,
    )
    if not selected_questions:
        _set_empty_pool_response_status(response, pool)
    return _unit_exercise_pool_payload(node=node, pool=pool, questions=selected_questions)


@router.get(
    "/api/learners/{learner_id}/knowledge-base/units/{curriculum_node_id}/exercise-pool"
)
async def get_unit_exercise_pool(
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    response: Response,
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
    pool = await get_exercise_pool(
        db,
        source_id=node.source_id,
        curriculum_node_id=node.id,
        learner_id=learner_id,
    )
    selected_questions = await select_unit_exercises_for_learner(
        db,
        learner_id=learner_id,
        questions=pool.questions,
        limit=limit,
    )
    if not selected_questions:
        _set_empty_pool_response_status(response, pool)
    return _unit_exercise_pool_payload(node=node, pool=pool, questions=selected_questions)


def _unit_exercise_pool_payload(
    *,
    node: CurriculumNode,
    pool: ExercisePoolSnapshot,
    questions: list[ExerciseQuestion],
) -> dict[str, Any]:
    run = pool.generation_run
    return {
        "curriculum_node_id": str(node.id),
        "title": f"{node.title} 练习",
        "questions": [
            _exercise_question_payload(question, target_label=node.title)
            for question in questions
        ],
        "pool": {
            "status": pool.status,
            "available_count": pool.available_count,
            "target_count": pool.target_count,
            "generation_run_id": str(run.id) if run is not None else None,
            "generation_status": run.status if run is not None else None,
            "retry_after_seconds": (
                2 if run is not None and pool.status in {"generating", "refreshing"} else None
            ),
        },
    }


def _set_empty_pool_response_status(
    response: Response,
    pool: ExercisePoolSnapshot,
) -> None:
    if pool.generation_run is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Retry-After"] = "2"


def _exercise_question_payload(question: ExerciseQuestion, *, target_label: str) -> dict[str, Any]:
    item = exercise_question_to_item(question, target_label=target_label)
    return {
        **item,
        "question_type": question.question_type,
        "stem": question.stem,
    }


def _task_spec_for_exercise(question: ExerciseQuestion) -> TaskSpec:
    target_type = "knowledge_point" if question.knowledge_point_id else "curriculum_node"
    target_id = question.knowledge_point_id or question.curriculum_node_id
    return TaskSpec(
        task_id=f"knowledge-exercise:{question.id}",
        task_type="practice_knowledge_point",
        source="textbook_guided",
        objective=f"完成教材练习：{question.stem[:80]}",
        target=TaskTarget(
            target_type=target_type,
            target_id=str(target_id),
            label=question.stem[:80],
            metadata={
                "question_id": str(question.id),
                "question_type": question.question_type,
                "curriculum_node_id": str(question.curriculum_node_id),
            },
        ),
        difficulty=str(question.difficulty),
        expected_output={"answer": "learner_submitted_answer", "grading_result": "score"},
        allowed_tools=[
            "exercise.grade",
            "mastery.update",
            "memory.write",
            "review.schedule",
            "verification.verify_episode",
        ],
        success_criteria=SuccessCriteria(min_accuracy=1.0, requires_explanation=True),
        verification_policy=VerificationPolicy(
            required_checks=[
                "exercise_attempt_saved",
                "grading_result_exists",
                "memory_event_written",
                "mastery_update_valid",
            ],
            require_evidence=True,
        ),
        metadata={
            "source_id": str(question.source_id),
            "question_id": str(question.id),
            "question_type": question.question_type,
        },
    )


async def _record_runtime_tool_call(
    runtime: EpisodeRuntime,
    episode,
    tool_calls: list,
    *,
    tool_name: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any] | None = None,
    status: str = "success",
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    tool_calls.append(
        await runtime.record_tool_call(
            episode_id=episode.id,
            episode=episode,
            tool_name=tool_name,
            input_hash=stable_json_hash(input_payload),
            output_hash=stable_json_hash(output_payload) if output_payload is not None else None,
            status=status,
            error=error,
            metadata=metadata,
        )
    )


async def _append_runtime_event(
    runtime: EpisodeRuntime,
    events: list,
    *,
    episode,
    learner_id: uuid.UUID,
    event_type: str,
    target_type: str | None,
    target_id: str | None,
    payload: dict[str, Any],
) -> None:
    events.append(
        await runtime.append_event(
            episode_id=episode.id,
            learner_id=learner_id,
            event_type=event_type,
            source_module="knowledge",
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
    )


async def _update_exercise_mastery_and_review(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    question: ExerciseQuestion,
    correct: bool,
    grading: dict[str, Any],
    body: ExerciseAnswerRequest,
    attempt_id: uuid.UUID,
    evidence_refs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, ReviewSchedule | None]:
    if question.knowledge_point_id is None:
        return None, None
    mastery_result = await MasteryEngine(db).update_from_attempt(
        AttemptSignal(
            learner_id=str(learner_id),
            target_type="knowledge_point",
            target_id=str(question.knowledge_point_id),
            correct=correct,
            score=grading.get("score"),
            error_type=grading.get("error_type"),
            hint_count=body.hint_used,
            retry_count=body.attempt_index,
            response_time_ms=body.response_time_ms,
            source="knowledge.exercise_attempt",
            evidence_refs=[EvidenceRef(**ref) for ref in evidence_refs],
            metadata={"attempt_id": str(attempt_id), "question_id": str(question.id)},
        )
    )
    review = ReviewSchedule(
        learner_id=learner_id,
        item_type="knowledge",
        item_id=question.knowledge_point_id,
        scheduled_at=mastery_result.next_review_at or datetime.now(timezone.utc),
        result="correct" if correct else "incorrect",
        response_time_ms=body.response_time_ms,
        confidence_before=mastery_result.previous_score,
        confidence_after=mastery_result.new_score,
        recommended_next_drill="textbook_review",
    )
    db.add(review)
    await db.flush()
    return (mastery_result.model_dump(mode="json"), review)


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
    runtime = EpisodeRuntime(db)
    runtime_events = []
    tool_calls = []
    task_spec = _task_spec_for_exercise(question)
    episode = await runtime.create_episode(
        learner_id=learner_id,
        source="textbook_guided",
        entrypoint="knowledge.exercise_attempt",
        task_spec=task_spec,
        status="running",
        context_snapshot={
            "question_id": str(question.id),
            "question_type": question.question_type,
            "session_id": str(body.session_id) if body.session_id else None,
        },
    )
    target_type = task_spec.target.target_type
    target_id = task_spec.target.target_id

    try:
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=learner_id,
            event_type="episode_started",
            target_type=target_type,
            target_id=target_id,
            payload={"task_id": task_spec.task_id, "question_id": str(question.id)},
        )
        grading = grade_exercise_answer(question, body.answer, attempt_index=body.attempt_index)
        await _record_runtime_tool_call(
            runtime,
            episode,
            tool_calls,
            tool_name="exercise.grade",
            input_payload={
                "question_id": str(question.id),
                "answer": body.answer,
                "attempt_index": body.attempt_index,
            },
            output_payload=grading,
        )
        correct = bool(grading["correct"])
        stored_answer = (
            body.answer if isinstance(body.answer, str) else json.dumps(body.answer, ensure_ascii=False)
        )
        attempt = await ExerciseAttemptService(db).save_knowledge_question_attempt(
            learner_id=learner_id,
            question=question,
            answer=stored_answer.strip(),
            correct=correct,
            session_id=body.session_id,
            response_time_ms=body.response_time_ms,
            metadata={
                "score": grading["score"],
                "passed": grading["passed"],
                "error_type": grading["error_type"],
                "hint_used": body.hint_used,
                "attempt_index": body.attempt_index,
                "next_review_signal": grading["next_review_signal"],
                "episode_id": str(episode.id),
            },
            source_context={
                "source_id": str(question.source_id),
                "episode_id": str(episode.id),
            },
        )
        evidence_refs = [
            evidence_from_attempt(attempt, reason="submitted exercise answer", used_by="runtime").model_dump(
                mode="json"
            )
        ]
        if question.knowledge_point_id:
            evidence_refs.append(
                EvidenceRef(
                    evidence_type="knowledge_point",
                    evidence_id=str(question.knowledge_point_id),
                    reason="exercise target",
                    used_by="runtime",
                ).model_dump(mode="json")
            )
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=learner_id,
            event_type="exercise_answered",
            target_type=target_type,
            target_id=target_id,
            payload={
                "question_id": str(question.id),
                "attempt_id": str(attempt.id),
                "answer": submitted_answer,
                "hint_used": body.hint_used,
                "attempt_index": body.attempt_index,
                "response_time_ms": body.response_time_ms,
                "evidence_refs": evidence_refs,
            },
        )
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=learner_id,
            event_type="exercise_graded",
            target_type=target_type,
            target_id=target_id,
            payload={
                "question_id": str(question.id),
                "attempt_id": str(attempt.id),
                "correct": correct,
                "score": grading["score"],
                "passed": grading["passed"],
                "error_type": grading["error_type"],
                "next_review_signal": grading["next_review_signal"],
                "evidence_refs": evidence_refs,
            },
        )

        mastery_update, review_schedule = await _update_exercise_mastery_and_review(
            db,
            learner_id=learner_id,
            question=question,
            correct=correct,
            grading=grading,
            body=body,
            attempt_id=attempt.id,
            evidence_refs=evidence_refs,
        )
        if mastery_update is not None:
            await _record_runtime_tool_call(
                runtime,
                episode,
                tool_calls,
                tool_name="mastery.update",
                input_payload={
                    "attempt_id": str(attempt.id),
                    "correct": correct,
                    "score": grading["score"],
                    "hint_count": body.hint_used,
                },
                output_payload=mastery_update,
            )
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=learner_id,
                event_type="mastery_updated",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload=mastery_update,
            )
        if review_schedule is not None:
            await _record_runtime_tool_call(
                runtime,
                episode,
                tool_calls,
                tool_name="review.schedule",
                input_payload={
                    "attempt_id": str(attempt.id),
                    "knowledge_point_id": str(question.knowledge_point_id),
                },
                output_payload={
                    "review_schedule_id": str(review_schedule.id),
                    "scheduled_at": review_schedule.scheduled_at.isoformat(),
                },
            )
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=learner_id,
                event_type="review_scheduled",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload={
                    "review_schedule_id": str(review_schedule.id),
                    "scheduled_at": review_schedule.scheduled_at.isoformat(),
                    "evidence_refs": evidence_refs,
                },
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
                        "attempt_id": str(attempt.id),
                        "episode_id": str(episode.id),
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
            memory_event = await MemoryWriter(db).record_event(
                MemoryEventInput(
                    learner_id=learner_id,
                    event_type="knowledge_exercise_answered",
                    skill="knowledge",
                    subskill=question.question_type,
                    source_type="exercise_attempt",
                    source_id=str(attempt.id),
                    session_id=body.session_id,
                    payload={
                        "question_id": str(question.id),
                        "attempt_id": str(attempt.id),
                        "episode_id": str(episode.id),
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
                        "evidence_refs": evidence_refs,
                    },
                    confidence=0.95,
                    occurred_at=now,
                )
            )
            memory_refs = [
                *evidence_refs,
                evidence_from_memory_event(
                    memory_event,
                    reason="memory evidence written for exercise",
                    used_by="runtime",
                ).model_dump(mode="json"),
            ]
            await _record_runtime_tool_call(
                runtime,
                episode,
                tool_calls,
                tool_name="memory.write",
                input_payload={"attempt_id": str(attempt.id), "event_type": "knowledge_exercise_answered"},
                output_payload={"memory_event_id": str(memory_event.id)},
            )
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=learner_id,
                event_type="memory_written",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload={
                    "memory_event_id": str(memory_event.id),
                    "attempt_id": str(attempt.id),
                    "evidence_refs": memory_refs,
                },
            )

        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=learner_id,
            event_type="episode_completed",
            target_type=target_type,
            target_id=target_id,
            payload={"task_id": task_spec.task_id},
        )
        trace = EpisodeTraceView(
            episode=episode_to_view(episode),
            events=[event_to_view(event) for event in runtime_events],
            tool_calls=[tool_call_to_view(tool_call) for tool_call in tool_calls],
        )
        verification_report = await verify_knowledge_exercise_episode(
            db,
            str(episode.id),
            trace=trace,
        )
        await _record_runtime_tool_call(
            runtime,
            episode,
            tool_calls,
            tool_name="verification.verify_episode",
            input_payload={"episode_id": str(episode.id)},
            output_payload=verification_report,
        )
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=learner_id,
            event_type="verification_report_generated",
            target_type=target_type,
            target_id=target_id,
            payload={
                "status": verification_report.get("status"),
                "required_checks": verification_report.get("required_checks") or [],
                "passed_count": verification_report.get("passed_count"),
                "failed_count": verification_report.get("failed_count"),
                "warning_count": verification_report.get("warning_count"),
                "critical_failed_count": verification_report.get("critical_failed_count"),
                "evidence_ref_count": verification_report.get("evidence_ref_count"),
                "evidence_refs": evidence_refs,
            },
        )
        await runtime.complete_episode(
            episode.id,
            episode=episode,
            verification_report=verification_report,
        )
        await db.flush()
    except Exception as exc:
        await runtime.fail_episode(
            episode.id,
            episode=episode,
            failure_type=exc.__class__.__name__,
            error_message=str(exc)[:500],
        )
        raise
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
        episode_id=str(episode.id),
        episode_trace_url=f"/api/runtime/episodes/{episode.id}",
        verification_status=verification_report.get("status"),
        runtime_events_count=len(runtime_events),
        verification_report=verification_report,
        mastery_update=mastery_update,
    )
