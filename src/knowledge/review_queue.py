from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.quality import quality_summary, score_textbook_quality
from src.models.knowledge import (
    ExerciseQuestion,
    KnowledgeChunk,
    KnowledgePoint,
    KnowledgeSource,
    ParserReviewItem,
)

LOW_CONFIDENCE_THRESHOLD = 0.75
PENDING_DECISION = "pending"


@dataclass(frozen=True)
class ReviewQueueSummary:
    pending_review_count: int
    pending_blocker_count: int
    review_warning_count: int

    def to_report_patch(self) -> dict[str, int]:
        return {
            "requires_review_count": self.pending_review_count,
            "pending_blocker_count": self.pending_blocker_count,
            "review_warning_count": self.review_warning_count,
        }


def build_parser_review_items(
    *,
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID | None,
    knowledge_points: list[KnowledgePoint] | tuple[KnowledgePoint, ...],
    report: dict[str, Any],
    quality_score: dict[str, Any] | Any,
) -> list[ParserReviewItem]:
    items: list[ParserReviewItem] = []
    signatures: set[tuple[str, str, str]] = set()
    dirty_tokens = [str(token) for token in report.get("dirty_tokens") or []]

    def add(
        *,
        target_type: str,
        target_id: uuid.UUID | None,
        issue_type: str,
        severity: str,
        evidence_snapshot: dict[str, Any] | None = None,
        suggested_fix: dict[str, Any] | None = None,
    ) -> None:
        key = (target_type, str(target_id or "source"), issue_type)
        if key in signatures:
            return
        signatures.add(key)
        items.append(
            ParserReviewItem(
                source_id=source_id,
                parser_run_id=parser_run_id,
                target_type=target_type,
                target_id=target_id,
                issue_type=issue_type,
                severity=severity,
                evidence_snapshot=_compact_evidence(evidence_snapshot or {}),
                suggested_fix=suggested_fix or {},
                decision=PENDING_DECISION,
            )
        )

    for point in knowledge_points:
        content = dict(point.content or {})
        evidence = _point_evidence(point)
        confidence = _float(content.get("confidence"))
        warnings = [str(item) for item in content.get("warnings") or []]
        if content.get("requires_review") or (
            confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD
        ):
            add(
                target_type="knowledge_point",
                target_id=point.id,
                issue_type="low_confidence",
                severity="warning",
                evidence_snapshot=evidence,
                suggested_fix={"action": "confirm_or_update", "fields": ["title", "summary", "source_page"]},
            )
        raw_line = str(content.get("raw_line") or "")
        if dirty_tokens and any(token in raw_line for token in dirty_tokens):
            add(
                target_type="knowledge_point",
                target_id=point.id,
                issue_type="dirty_token",
                severity="warning",
                evidence_snapshot=evidence,
                suggested_fix={"action": "update", "fields": ["title", "summary", "content.raw_line"]},
            )
        source_page = str(content.get("source_page") or point.source_page or "").strip()
        if not source_page:
            add(
                target_type="knowledge_point",
                target_id=point.id,
                issue_type="missing_source_page",
                severity="blocker",
                evidence_snapshot=evidence,
                suggested_fix={"action": "update", "fields": ["source_page"]},
            )
        if not _has_evidence(content, point):
            add(
                target_type="knowledge_point",
                target_id=point.id,
                issue_type="missing_evidence",
                severity="warning",
                evidence_snapshot=evidence,
                suggested_fix={"action": "update", "fields": ["content.evidence_refs", "content.raw_line"]},
            )
        for warning in warnings:
            if "schema" in warning.casefold():
                add(
                    target_type="knowledge_point",
                    target_id=point.id,
                    issue_type="schema_invalid",
                    severity="warning",
                    evidence_snapshot=evidence,
                    suggested_fix={"action": "update", "fields": ["content"]},
                )

    for duplicate in _duplicate_points(knowledge_points):
        add(
            target_type="knowledge_point",
            target_id=duplicate.id,
            issue_type="duplicate",
            severity="warning",
            evidence_snapshot=_point_evidence(duplicate),
            suggested_fix={"action": "ignore_or_update", "fields": ["title", "summary"]},
        )

    _add_coverage_gap_items(add, report)
    _add_quality_blocker_items(add, quality_score)
    return items


async def replace_parser_review_items(
    db: AsyncSession,
    *,
    source: KnowledgeSource,
    parser_run_id: uuid.UUID,
    knowledge_points: list[KnowledgePoint],
    report: dict[str, Any],
    quality_score: dict[str, Any],
) -> list[ParserReviewItem]:
    await db.execute(
        delete(ParserReviewItem).where(
            ParserReviewItem.source_id == source.id,
            ParserReviewItem.parser_run_id == parser_run_id,
        )
    )
    items = build_parser_review_items(
        source_id=source.id,
        parser_run_id=parser_run_id,
        knowledge_points=knowledge_points,
        report=report,
        quality_score=quality_score,
    )
    for item in items:
        db.add(item)
    return items


def queue_summary(items: list[ParserReviewItem] | tuple[ParserReviewItem, ...]) -> ReviewQueueSummary:
    pending = [item for item in items if item.decision == PENDING_DECISION]
    return ReviewQueueSummary(
        pending_review_count=len(pending),
        pending_blocker_count=sum(1 for item in pending if item.severity == "blocker"),
        review_warning_count=sum(1 for item in pending if item.severity == "warning"),
    )


async def load_review_queue_summary(db: AsyncSession, source_id: uuid.UUID) -> ReviewQueueSummary:
    result = await db.execute(select(ParserReviewItem).where(ParserReviewItem.source_id == source_id))
    return queue_summary(list(result.scalars().all()))


def apply_quality_gate(
    source: KnowledgeSource,
    *,
    summary: ReviewQueueSummary,
) -> dict[str, Any]:
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
        }
    report.update(summary.to_report_patch())
    score = score_textbook_quality(report)
    metadata["parser_report"] = report
    metadata.update(quality_summary(score, report))
    metadata["pending_blocker_count"] = summary.pending_blocker_count
    metadata["review_warning_count"] = summary.review_warning_count
    source.metadata_ = metadata
    source.status = "completed"
    return report


async def recalculate_quality_gate_from_queue(
    db: AsyncSession,
    source: KnowledgeSource,
) -> ReviewQueueSummary:
    summary = await load_review_queue_summary(db, source.id)
    apply_quality_gate(source, summary=summary)
    return summary


def mark_target_reviewed(target: Any, *, decision: str, learner_id: uuid.UUID, note: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if isinstance(target, KnowledgePoint):
        content = dict(target.content or {})
        content["requires_review"] = False
        content["review_decision"] = decision
        content["reviewed_at"] = now
        content["reviewed_by_learner_id"] = str(learner_id)
        if note:
            content["review_note"] = note
        target.content = content
    elif isinstance(target, ExerciseQuestion):
        metadata = dict(target.metadata_ or {})
        metadata["requires_review"] = False
        metadata["review_decision"] = decision
        metadata["reviewed_at"] = now
        if note:
            metadata["review_note"] = note
        target.metadata_ = metadata
    elif isinstance(target, KnowledgeChunk):
        metadata = dict(target.metadata_ or {})
        metadata["requires_review"] = False
        metadata["review_decision"] = decision
        metadata["reviewed_at"] = now
        if note:
            metadata["review_note"] = note
        target.metadata_ = metadata


def _point_evidence(point: KnowledgePoint) -> dict[str, Any]:
    content = dict(point.content or {})
    return {
        "title": point.title,
        "type": point.type,
        "source_page": content.get("source_page") or point.source_page,
        "confidence": content.get("confidence"),
        "warnings": content.get("warnings") or [],
        "raw_line": content.get("raw_line"),
        "parser_run_id": content.get("parser_run_id"),
        "origin": content.get("origin"),
    }


def _compact_evidence(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "title",
        "type",
        "source_page",
        "confidence",
        "warnings",
        "raw_line",
        "parser_run_id",
        "origin",
        "reason",
        "metric",
        "value",
        "threshold",
    }
    return {key: value.get(key) for key in allowed if key in value and value.get(key) is not None}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_evidence(content: dict[str, Any], point: KnowledgePoint) -> bool:
    return bool(
        content.get("raw_line")
        or content.get("evidence_refs")
        or content.get("evidence_pdf_pages")
        or content.get("origin")
        or point.source_page
    )


def _duplicate_points(
    knowledge_points: list[KnowledgePoint] | tuple[KnowledgePoint, ...],
) -> list[KnowledgePoint]:
    seen: set[tuple[str, str]] = set()
    duplicates: list[KnowledgePoint] = []
    for point in knowledge_points:
        key = (point.type, " ".join(point.title.casefold().split()))
        if key in seen:
            duplicates.append(point)
        seen.add(key)
    return duplicates


def _add_coverage_gap_items(add: Any, report: dict[str, Any]) -> None:
    checks = [
        ("source_page_coverage_rate", 0.95, 0.5),
        ("evidence_ref_coverage_rate", 0.9, 0.5),
        ("core_vocabulary_hit_rate", 0.9, 0.25),
        ("rag_page_coverage_rate", 0.95, 0.5),
    ]
    for metric, warning_threshold, blocker_threshold in checks:
        value = _float(report.get(metric))
        if value is None or value >= warning_threshold:
            continue
        add(
            target_type="source",
            target_id=None,
            issue_type="coverage_gap",
            severity="blocker" if value < blocker_threshold else "warning",
            evidence_snapshot={
                "metric": metric,
                "value": value,
                "threshold": warning_threshold,
            },
            suggested_fix={"action": "inspect_parser_output", "metric": metric},
        )


def _add_quality_blocker_items(add: Any, quality_score: dict[str, Any] | Any) -> None:
    if not isinstance(quality_score, dict):
        quality_score = quality_score.to_dict()
    for reason in quality_score.get("blocking_reasons") or []:
        add(
            target_type="source",
            target_id=None,
            issue_type="quality_gate_blocker",
            severity="blocker",
            evidence_snapshot={"reason": reason},
            suggested_fix={"action": "fix_blocking_reason"},
        )
