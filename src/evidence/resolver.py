import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.types import EvidenceBundle, EvidenceRef, EvidenceResolution
from src.models.knowledge import ExerciseAttempt, KnowledgeChunk, KnowledgePoint
from src.models.memory import LearningMemoryEvent
from src.models.runtime import LearningEvent


class EvidenceResolver:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_ref(self, ref: EvidenceRef) -> EvidenceResolution:
        model = _EVIDENCE_MODELS.get(ref.evidence_type)
        if model is None:
            return EvidenceResolution(ref=ref, found=False, metadata={"reason": "unsupported_type"})
        object_id = _safe_uuid(ref.evidence_id)
        if object_id is None:
            return EvidenceResolution(ref=ref, found=False, metadata={"reason": "invalid_id"})

        result = await self.db.execute(select(model).where(model.id == object_id))
        item = result.scalar_one_or_none()
        if item is None:
            return EvidenceResolution(ref=ref, found=False)
        return _resolution_for_item(ref, item)

    async def resolve_bundle(self, bundle: EvidenceBundle) -> list[EvidenceResolution]:
        return [await self.resolve_ref(ref) for ref in bundle.refs]


def evidence_from_attempt(attempt, *, reason: str | None = None, used_by: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        evidence_type="exercise_attempt",
        evidence_id=str(attempt.id),
        reason=reason,
        used_by=used_by,
        metadata={
            "target_type": getattr(attempt, "target_type", None),
            "target_id": getattr(attempt, "target_id", None),
            "correct": getattr(attempt, "correct", None),
        },
    )


def evidence_from_memory_event(
    memory_event,
    *,
    reason: str | None = None,
    used_by: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_type="memory_event",
        evidence_id=str(memory_event.id),
        reason=reason,
        used_by=used_by,
        metadata={"event_type": getattr(memory_event, "event_type", None)},
    )


def evidence_from_rag_chunk(chunk, *, reason: str | None = None, used_by: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        evidence_type="rag_chunk",
        evidence_id=str(getattr(chunk, "id", getattr(chunk, "chunk_id", ""))),
        reason=reason,
        used_by=used_by,
        metadata={
            "source_id": str(getattr(chunk, "source_id", "")),
            "page_number": getattr(chunk, "page_number", None),
        },
    )


def evidence_from_knowledge_point(
    kp,
    *,
    reason: str | None = None,
    used_by: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_type="knowledge_point",
        evidence_id=str(kp.id),
        reason=reason,
        used_by=used_by,
        metadata={"type": getattr(kp, "type", None), "source_page": getattr(kp, "source_page", None)},
    )


def evidence_from_learning_event(
    event,
    *,
    reason: str | None = None,
    used_by: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_type="learning_event",
        evidence_id=str(event.id),
        reason=reason,
        used_by=used_by,
        metadata={"event_type": getattr(event, "event_type", None)},
    )


_EVIDENCE_MODELS = {
    "knowledge_point": KnowledgePoint,
    "exercise_attempt": ExerciseAttempt,
    "memory_event": LearningMemoryEvent,
    "rag_chunk": KnowledgeChunk,
    "learning_event": LearningEvent,
}


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _resolution_for_item(ref: EvidenceRef, item: Any) -> EvidenceResolution:
    if isinstance(item, KnowledgePoint):
        return EvidenceResolution(
            ref=ref,
            found=True,
            title=item.title,
            content=item.summary,
            source=f"knowledge_point:{item.source_page}",
            metadata={
                "type": item.type,
                "curriculum_node_id": str(item.curriculum_node_id),
                "source_id": str(item.source_id),
            },
        )
    if isinstance(item, ExerciseAttempt):
        return EvidenceResolution(
            ref=ref,
            found=True,
            title=item.target_label,
            content=item.answer,
            source=f"exercise_attempt:{item.exercise_id}",
            metadata={
                "correct": item.correct,
                "result": item.result,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "metadata": item.metadata_ or {},
            },
        )
    if isinstance(item, LearningMemoryEvent):
        return EvidenceResolution(
            ref=ref,
            found=True,
            title=item.event_type,
            content=_json_summary(item.payload),
            source=f"{item.source_type}:{item.source_id}" if item.source_id else item.source_type,
            metadata={
                "skill": item.skill,
                "subskill": item.subskill,
                "confidence": item.confidence,
                "occurred_at": item.occurred_at.isoformat(),
            },
        )
    if isinstance(item, KnowledgeChunk):
        return EvidenceResolution(
            ref=ref,
            found=True,
            title=f"Page {item.page_number} chunk {item.chunk_index}",
            content=item.content,
            source=f"knowledge_chunk:{item.source_id}",
            metadata={
                "curriculum_node_id": str(item.curriculum_node_id) if item.curriculum_node_id else None,
                "page_number": item.page_number,
                "chunk_index": item.chunk_index,
            },
        )
    if isinstance(item, LearningEvent):
        return EvidenceResolution(
            ref=ref,
            found=True,
            title=item.event_type,
            content=_json_summary(item.payload),
            source=f"episode:{item.episode_id}",
            metadata={
                "source_module": item.source_module,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "occurred_at": item.occurred_at.isoformat(),
            },
        )
    return EvidenceResolution(ref=ref, found=False, metadata={"reason": "unhandled_model"})


def _json_summary(payload: dict[str, Any]) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)[:1000]
