from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.runtime.events import LearningEventView


class AgentEpisodeView(BaseModel):
    id: str
    learner_id: str
    source: str
    entrypoint: str
    status: str
    task_spec: dict[str, Any]
    context_snapshot: dict[str, Any] | None = None
    memory_context_ids: list[str] | None = None
    rag_chunk_ids: list[str] | None = None
    tool_call_ids: list[str] | None = None
    verification_report: dict[str, Any] | None = None
    failure_type: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ToolCallRecordView(BaseModel):
    id: str
    episode_id: str
    tool_name: str
    input_hash: str
    output_hash: str | None = None
    latency_ms: int | None = None
    status: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EpisodeTraceView(BaseModel):
    episode: AgentEpisodeView
    events: list[LearningEventView]
    tool_calls: list[ToolCallRecordView]
    checkpoint: dict[str, Any] | None = None


def episode_to_view(episode) -> AgentEpisodeView:
    now = datetime.now(timezone.utc)
    started_at = episode.started_at or now
    return AgentEpisodeView(
        id=str(episode.id),
        learner_id=str(episode.learner_id),
        source=episode.source,
        entrypoint=episode.entrypoint,
        status=episode.status,
        task_spec=episode.task_spec or {},
        context_snapshot=episode.context_snapshot,
        memory_context_ids=episode.memory_context_ids,
        rag_chunk_ids=episode.rag_chunk_ids,
        tool_call_ids=episode.tool_call_ids,
        verification_report=episode.verification_report,
        failure_type=episode.failure_type,
        error_message=episode.error_message,
        started_at=started_at,
        completed_at=episode.completed_at,
        created_at=episode.created_at or started_at,
        updated_at=episode.updated_at or episode.completed_at or started_at,
    )


def event_to_view(event) -> LearningEventView:
    return LearningEventView(
        id=str(event.id),
        episode_id=str(event.episode_id),
        learner_id=str(event.learner_id),
        event_type=event.event_type,
        source_module=event.source_module,
        target_type=event.target_type,
        target_id=event.target_id,
        payload=event.payload or {},
        occurred_at=event.occurred_at,
    )


def tool_call_to_view(tool_call) -> ToolCallRecordView:
    return ToolCallRecordView(
        id=str(tool_call.id),
        episode_id=str(tool_call.episode_id),
        tool_name=tool_call.tool_name,
        input_hash=tool_call.input_hash,
        output_hash=tool_call.output_hash,
        latency_ms=tool_call.latency_ms,
        status=tool_call.status,
        error=tool_call.error,
        metadata=tool_call.metadata_ or {},
        created_at=tool_call.created_at or datetime.now(timezone.utc),
    )
