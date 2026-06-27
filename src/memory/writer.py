import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.layers import MemoryLayer
from src.memory.policies import clamp_confidence, clean_payload, normalize_skill
from src.memory.schemas import MemoryEventInput, MemoryOperationInput
from src.models.memory import LearningMemoryEvent, MemoryOperation


class MemoryWriter:
    """Hot-path writer for auditable learning memory events and user operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_event(self, event: MemoryEventInput, *, commit: bool = False) -> LearningMemoryEvent:
        payload = clean_payload(event.payload)
        if "evidence_ref" not in payload:
            source = event.source_type.strip() or "system"
            payload["evidence_ref"] = f"{source}:{event.source_id}" if event.source_id else source
        payload.setdefault("memory_layer", MemoryLayer.EVIDENCE.value)
        row = LearningMemoryEvent(
            learner_id=event.learner_id,
            event_type=event.event_type.strip(),
            skill=normalize_skill(event.skill),
            subskill=event.subskill.strip().lower() if event.subskill else None,
            source_type=event.source_type.strip() or "system",
            source_id=str(event.source_id) if event.source_id else None,
            thread_id=event.thread_id,
            session_id=event.session_id,
            payload=payload,
            confidence=clamp_confidence(event.confidence),
            visibility=event.visibility,
            created_by=event.created_by,
            occurred_at=event.occurred_at or datetime.now(timezone.utc),
        )
        self.db.add(row)
        await self.db.flush()
        if commit:
            await self.db.commit()
        return row

    async def record_operation(
        self, operation: MemoryOperationInput, *, commit: bool = False
    ) -> MemoryOperation:
        row = MemoryOperation(
            learner_id=operation.learner_id,
            operation_type=operation.operation_type,
            target_type=operation.target_type,
            target_id=str(operation.target_id) if operation.target_id else None,
            before=operation.before or {},
            after=operation.after or {},
            reason=operation.reason,
            created_by=operation.created_by,
        )
        self.db.add(row)
        await self.db.flush()
        if commit:
            await self.db.commit()
        return row

    async def record_user_control_event(
        self,
        *,
        learner_id: uuid.UUID,
        operation_type: str,
        target_type: str,
        target_id: str | uuid.UUID | None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
        commit: bool = False,
    ) -> tuple[LearningMemoryEvent, MemoryOperation]:
        operation = await self.record_operation(
            MemoryOperationInput(
                learner_id=learner_id,
                operation_type=operation_type,
                target_type=target_type,
                target_id=str(target_id) if target_id else None,
                before=before,
                after=after,
                reason=reason,
            )
        )
        event_type = {
            "delete": "user_deleted_memory",
            "correct": "user_corrected_memory",
            "disable": "user_disabled_memory",
            "mark_improved": "user_marked_memory_improved",
            "mark_mastered": "user_marked_mastered",
            "reset_plan": "user_reset_learning_plan",
        }.get(operation_type, "user_corrected_memory")
        event = await self.record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type=event_type,
                skill=(after or before or {}).get("skill", "general"),
                source_type=target_type,
                source_id=str(target_id) if target_id else None,
                payload={
                    "operation_id": str(operation.id),
                    "operation_type": operation_type,
                    "governance_layer": MemoryLayer.GOVERNANCE.value,
                    "before": before or {},
                    "after": after or {},
                    "reason": reason,
                },
                confidence=1.0,
                created_by="user",
            )
        )
        if commit:
            await self.db.commit()
        return event, operation
