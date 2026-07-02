import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.graph_checkpoint import LearningGraphCheckpoint


class GraphCheckpointStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_waiting_checkpoint(
        self,
        *,
        learner_id: str | uuid.UUID,
        episode_id: str | uuid.UUID,
        thread_id: str | None,
        checkpoint_key: str,
        resume_from: str | None,
        state_snapshot: dict[str, Any],
        required_input_schema: dict[str, Any] | None,
        prompt_payload: dict[str, Any] | None,
    ) -> LearningGraphCheckpoint:
        existing = await self.get_active_checkpoint(episode_id, learner_id)
        if existing is not None:
            return existing

        checkpoint = LearningGraphCheckpoint(
            learner_id=_as_uuid(learner_id),
            episode_id=_as_uuid(episode_id),
            thread_id=thread_id,
            checkpoint_key=checkpoint_key,
            status="waiting_user",
            resume_from=resume_from,
            state_snapshot=state_snapshot,
            required_input_schema=required_input_schema,
            prompt_payload=prompt_payload,
        )
        self.db.add(checkpoint)
        await self.db.flush()
        if getattr(checkpoint, "id", None) is None:
            checkpoint.id = uuid.uuid4()
        return checkpoint

    async def get_active_checkpoint(
        self,
        episode_id: str | uuid.UUID,
        learner_id: str | uuid.UUID,
    ) -> LearningGraphCheckpoint | None:
        result = await self.db.execute(
            select(LearningGraphCheckpoint)
            .where(
                LearningGraphCheckpoint.episode_id == _as_uuid(episode_id),
                LearningGraphCheckpoint.learner_id == _as_uuid(learner_id),
                LearningGraphCheckpoint.status == "waiting_user",
            )
            .order_by(LearningGraphCheckpoint.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_resumed(
        self,
        checkpoint_id: str | uuid.UUID,
    ) -> LearningGraphCheckpoint:
        checkpoint = await self._get_checkpoint(checkpoint_id)
        checkpoint.status = "resumed"
        checkpoint.consumed_at = checkpoint.consumed_at or datetime.now(timezone.utc)
        await self.db.flush()
        return checkpoint

    async def mark_completed(
        self,
        checkpoint_id: str | uuid.UUID,
    ) -> LearningGraphCheckpoint:
        checkpoint = await self._get_checkpoint(checkpoint_id)
        checkpoint.status = "completed"
        checkpoint.consumed_at = checkpoint.consumed_at or datetime.now(timezone.utc)
        await self.db.flush()
        return checkpoint

    async def mark_failed(
        self,
        checkpoint_id: str | uuid.UUID,
        reason: str,
    ) -> LearningGraphCheckpoint:
        checkpoint = await self._get_checkpoint(checkpoint_id)
        snapshot = dict(checkpoint.state_snapshot or {})
        snapshot["failure_reason"] = reason
        checkpoint.state_snapshot = snapshot
        checkpoint.status = "failed"
        checkpoint.consumed_at = checkpoint.consumed_at or datetime.now(timezone.utc)
        await self.db.flush()
        return checkpoint

    async def list_checkpoints_for_episode(
        self,
        episode_id: str | uuid.UUID,
    ) -> list[LearningGraphCheckpoint]:
        result = await self.db.execute(
            select(LearningGraphCheckpoint)
            .where(LearningGraphCheckpoint.episode_id == _as_uuid(episode_id))
            .order_by(LearningGraphCheckpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_checkpoint(
        self,
        checkpoint_id: str | uuid.UUID,
    ) -> LearningGraphCheckpoint:
        result = await self.db.execute(
            select(LearningGraphCheckpoint).where(
                LearningGraphCheckpoint.id == _as_uuid(checkpoint_id)
            )
        )
        checkpoint = result.scalar_one_or_none()
        if checkpoint is None:
            raise LookupError("LearningGraphCheckpoint not found")
        return checkpoint


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
