import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
from src.runtime.events import LearningEventCreate
from src.runtime.schemas import (
    EpisodeTraceView,
    episode_to_view,
    event_to_view,
    tool_call_to_view,
)
from src.runtime.task_spec import TaskSpec


class EpisodeRuntime:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_episode(
        self,
        *,
        learner_id: str | uuid.UUID,
        source: str,
        entrypoint: str,
        task_spec: TaskSpec,
        context_snapshot: dict[str, Any] | None = None,
        memory_context_ids: list[str] | None = None,
        rag_chunk_ids: list[str] | None = None,
        status: str = "created",
    ) -> AgentEpisode:
        episode = AgentEpisode(
            learner_id=_as_uuid(learner_id),
            source=source,
            entrypoint=entrypoint,
            status=status,
            task_spec=task_spec.model_dump(mode="json"),
            context_snapshot=context_snapshot,
            memory_context_ids=memory_context_ids,
            rag_chunk_ids=rag_chunk_ids,
            tool_call_ids=[],
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(episode)
        await self.db.flush()
        if getattr(episode, "id", None) is None:
            episode.id = uuid.uuid4()
        return episode

    async def append_event(
        self,
        event: LearningEventCreate | None = None,
        *,
        episode_id: str | uuid.UUID | None = None,
        learner_id: str | uuid.UUID | None = None,
        event_type: str | None = None,
        source_module: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> LearningEvent:
        if event is not None:
            episode_id = event.episode_id
            learner_id = event.learner_id
            event_type = event.event_type
            source_module = event.source_module
            target_type = event.target_type
            target_id = event.target_id
            payload = event.payload
        if episode_id is None or learner_id is None or event_type is None or source_module is None:
            raise ValueError("episode_id, learner_id, event_type, and source_module are required")

        row = LearningEvent(
            episode_id=_as_uuid(episode_id),
            learner_id=_as_uuid(learner_id),
            event_type=event_type,
            source_module=source_module,
            target_type=target_type,
            target_id=target_id,
            payload=payload or {},
            occurred_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        await self.db.flush()
        if getattr(row, "id", None) is None:
            row.id = uuid.uuid4()
        return row

    async def record_tool_call(
        self,
        *,
        episode_id: str | uuid.UUID,
        tool_name: str,
        input_hash: str,
        output_hash: str | None = None,
        latency_ms: int | None = None,
        status: str = "success",
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        episode: AgentEpisode | None = None,
    ) -> ToolCallRecord:
        row = ToolCallRecord(
            episode_id=_as_uuid(episode_id),
            tool_name=tool_name,
            input_hash=input_hash,
            output_hash=output_hash,
            latency_ms=latency_ms,
            status=status,
            error=error,
            metadata_=metadata or {},
        )
        self.db.add(row)
        await self.db.flush()
        if getattr(row, "id", None) is None:
            row.id = uuid.uuid4()

        target_episode = episode or await self._get_episode(episode_id)
        ids = list(target_episode.tool_call_ids or [])
        ids.append(str(row.id))
        target_episode.tool_call_ids = ids
        await self.db.flush()
        return row

    async def complete_episode(
        self,
        episode_id: str | uuid.UUID,
        *,
        verification_report: dict[str, Any] | None = None,
        episode: AgentEpisode | None = None,
    ) -> AgentEpisode:
        target_episode = episode or await self._get_episode(episode_id)
        target_episode.status = "completed"
        target_episode.completed_at = datetime.now(timezone.utc)
        if verification_report is not None:
            target_episode.verification_report = verification_report
        await self.db.flush()
        return target_episode

    async def fail_episode(
        self,
        episode_id: str | uuid.UUID,
        *,
        failure_type: str,
        error_message: str,
        episode: AgentEpisode | None = None,
    ) -> AgentEpisode:
        target_episode = episode or await self._get_episode(episode_id)
        target_episode.status = "failed"
        target_episode.completed_at = datetime.now(timezone.utc)
        target_episode.failure_type = failure_type
        target_episode.error_message = error_message
        await self.db.flush()
        return target_episode

    async def get_episode_trace(self, episode_id: str | uuid.UUID) -> EpisodeTraceView:
        episode = await self._get_episode(episode_id)
        events_result = await self.db.execute(
            select(LearningEvent)
            .where(LearningEvent.episode_id == episode.id)
            .order_by(LearningEvent.occurred_at.asc(), LearningEvent.created_at.asc())
        )
        tool_result = await self.db.execute(
            select(ToolCallRecord)
            .where(ToolCallRecord.episode_id == episode.id)
            .order_by(ToolCallRecord.created_at.asc())
        )
        return EpisodeTraceView(
            episode=episode_to_view(episode),
            events=[event_to_view(event) for event in events_result.scalars().all()],
            tool_calls=[tool_call_to_view(tool) for tool in tool_result.scalars().all()],
        )

    async def _get_episode(self, episode_id: str | uuid.UUID) -> AgentEpisode:
        result = await self.db.execute(
            select(AgentEpisode).where(AgentEpisode.id == _as_uuid(episode_id))
        )
        episode = result.scalar_one_or_none()
        if episode is None:
            raise LookupError("AgentEpisode not found")
        return episode


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
