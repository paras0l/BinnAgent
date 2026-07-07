import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.group_learning import GroupLearningMessage, GroupLearningSignal, GroupLearningSource
from src.prompts.executor import PromptExecutionContext, PromptExecutor
from src.providers.router import router as model_router


@dataclass(frozen=True)
class GroupLearningLlmAnalysisResult:
    source_id: uuid.UUID
    learner_id: uuid.UUID
    analyzed_message_count: int
    generated_signal_count: int
    skipped_signal_count: int
    remaining_pending_count: int


async def analyze_pending_group_learning_messages(
    db: AsyncSession,
    *,
    source: GroupLearningSource,
    limit: int = 10,
    executor: PromptExecutor | None = None,
) -> GroupLearningLlmAnalysisResult:
    batch_size = max(1, min(limit, 20))
    messages = await _pending_messages(db, source, batch_size)
    if not messages:
        return GroupLearningLlmAnalysisResult(
            source_id=source.id,
            learner_id=source.learner_id,
            analyzed_message_count=0,
            generated_signal_count=0,
            skipped_signal_count=0,
            remaining_pending_count=await _pending_count(db, source),
        )

    prompt_executor = executor or PromptExecutor(db=db, model_router=model_router)
    result = await prompt_executor.execute(
        prompt_id="group_learning.signal_extract",
        variables={"messages": [_message_payload(message) for message in messages]},
        context=PromptExecutionContext(
            learner_id=source.learner_id,
            source_module="group_learning",
            target_type="group_learning_source",
            target_id=source.id,
            metadata={"batch_size": len(messages), "platform": source.platform},
        ),
    )
    if result.validated_output is None:
        return GroupLearningLlmAnalysisResult(
            source_id=source.id,
            learner_id=source.learner_id,
            analyzed_message_count=0,
            generated_signal_count=0,
            skipped_signal_count=len(messages),
            remaining_pending_count=await _pending_count(db, source),
        )

    generated_count = 0
    skipped_count = 0
    message_by_id = {str(message.id): message for message in messages}
    for signal_payload in result.validated_output.get("signals") or []:
        message = message_by_id.get(str(signal_payload.get("message_id") or ""))
        if message is None:
            skipped_count += 1
            continue
        if await _signal_exists(db, message.id, signal_payload):
            skipped_count += 1
            continue
        signal = _signal_from_payload(source, message, signal_payload)
        if signal is None:
            skipped_count += 1
            continue
        db.add(signal)
        generated_count += 1

    now = datetime.now(timezone.utc)
    for message in messages:
        message.ingestion_status = "llm_analyzed"
        message.processed_at = now

    await db.flush()
    return GroupLearningLlmAnalysisResult(
        source_id=source.id,
        learner_id=source.learner_id,
        analyzed_message_count=len(messages),
        generated_signal_count=generated_count,
        skipped_signal_count=skipped_count,
        remaining_pending_count=await _pending_count(db, source),
    )


async def _pending_messages(
    db: AsyncSession,
    source: GroupLearningSource,
    limit: int,
) -> list[GroupLearningMessage]:
    result = await db.execute(
        select(GroupLearningMessage)
        .where(
            GroupLearningMessage.source_id == source.id,
            GroupLearningMessage.learner_id == source.learner_id,
            GroupLearningMessage.ingestion_status == "pending_llm_analysis",
        )
        .order_by(GroupLearningMessage.occurred_at.asc(), GroupLearningMessage.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _pending_count(db: AsyncSession, source: GroupLearningSource) -> int:
    result = await db.execute(
        select(GroupLearningMessage.id).where(
            GroupLearningMessage.source_id == source.id,
            GroupLearningMessage.learner_id == source.learner_id,
            GroupLearningMessage.ingestion_status == "pending_llm_analysis",
        )
    )
    return len(result.scalars().all())


def _message_payload(message: GroupLearningMessage) -> dict[str, Any]:
    return {
        "message_id": str(message.id),
        "external_message_id": message.external_message_id,
        "sender": message.external_member_key,
        "occurred_at": message.occurred_at.isoformat(),
        "text": message.content_text,
    }


async def _signal_exists(
    db: AsyncSession,
    message_id: uuid.UUID,
    payload: dict[str, Any],
) -> bool:
    result = await db.execute(
        select(GroupLearningSignal.id).where(
            GroupLearningSignal.message_id == message_id,
            GroupLearningSignal.signal_type == str(payload.get("signal_type") or ""),
            GroupLearningSignal.target_type == str(payload.get("target_type") or ""),
            GroupLearningSignal.target_label == str(payload.get("target_label") or ""),
        )
    )
    return result.scalar_one_or_none() is not None


def _signal_from_payload(
    source: GroupLearningSource,
    message: GroupLearningMessage,
    payload: dict[str, Any],
) -> GroupLearningSignal | None:
    signal_type = str(payload.get("signal_type") or "").strip()
    target_type = str(payload.get("target_type") or "").strip()
    target_label = str(payload.get("target_label") or "").strip()
    evidence_text = str(payload.get("evidence_text") or message.content_text).strip()
    recommendation_reason = str(payload.get("recommendation_reason") or "").strip()
    if not signal_type or not target_type or not target_label or not recommendation_reason:
        return None
    confidence = payload.get("confidence")
    if not isinstance(confidence, int | float):
        confidence = 0.75
    return GroupLearningSignal(
        message_id=message.id,
        learner_id=source.learner_id,
        signal_type=signal_type,
        target_type=target_type,
        target_label=target_label,
        confidence=max(0, min(float(confidence), 1)),
        evidence_text=evidence_text,
        normalized_note=str(payload.get("normalized_note") or "") or None,
        recommendation_reason=recommendation_reason,
        status="candidate",
        metadata_={"llm_extracted": True},
    )
