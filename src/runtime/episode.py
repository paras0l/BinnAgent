import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.types import EvidenceRef
from src.models.graph_checkpoint import LearningGraphCheckpoint
from src.models.prompt_execution import PromptExecutionRecord
from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
from src.runtime.events import LearningEventCreate
from src.runtime.schemas import (
    EpisodeTraceView,
    episode_to_view,
    event_to_view,
    prompt_execution_to_view,
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
        target_episode.status = status_for_verification_report(verification_report)
        target_episode.completed_at = datetime.now(timezone.utc)
        if verification_report is not None:
            target_episode.verification_report = verification_report
            if target_episode.status == "verification_failed":
                target_episode.failure_type = "verification_failed"
                target_episode.error_message = str(
                    verification_report.get("failed_reason") or "VerificationReport failed"
                )[:500]
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
        prompt_result = await self.db.execute(
            select(PromptExecutionRecord)
            .where(PromptExecutionRecord.episode_id == episode.id)
            .order_by(PromptExecutionRecord.created_at.asc())
        )
        checkpoint_result = await self.db.execute(
            select(LearningGraphCheckpoint)
            .where(LearningGraphCheckpoint.episode_id == episode.id)
            .order_by(LearningGraphCheckpoint.created_at.desc())
            .limit(1)
        )
        checkpoint = checkpoint_result.scalar_one_or_none()
        events = [event_to_view(event) for event in events_result.scalars().all()]
        tool_calls = [tool_call_to_view(tool) for tool in tool_result.scalars().all()]
        prompt_executions = [
            prompt_execution_to_view(record) for record in prompt_result.scalars().all()
        ]
        checkpoint_view = checkpoint_to_view(checkpoint) if checkpoint is not None else None
        episode_view = episode_to_view(episode)
        return EpisodeTraceView(
            episode=episode_view,
            events=events,
            tool_calls=tool_calls,
            checkpoint=checkpoint_view,
            verification_report=episode.verification_report,
            graph_run=graph_run_to_view(episode, checkpoint_view, prompt_executions),
            prompt_executions=prompt_executions,
            evidence_refs=collect_evidence_refs_from_events(events),
            node_summaries=node_summaries_from_trace(events, tool_calls, prompt_executions),
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


def checkpoint_to_view(checkpoint: LearningGraphCheckpoint) -> dict[str, Any]:
    state_snapshot = checkpoint.state_snapshot if isinstance(checkpoint.state_snapshot, dict) else {}
    prompt_payload = checkpoint.prompt_payload if isinstance(checkpoint.prompt_payload, dict) else {}
    return {
        "checkpoint_id": str(checkpoint.id),
        "learner_id": str(checkpoint.learner_id),
        "episode_id": str(checkpoint.episode_id),
        "thread_id": checkpoint.thread_id,
        "checkpoint_key": checkpoint.checkpoint_key,
        "status": checkpoint.status,
        "resume_from": checkpoint.resume_from,
        "answer_required": checkpoint.status == "waiting_user",
        "current_task_id": state_snapshot.get("current_task_id") or prompt_payload.get("task_id"),
        "required_input_schema": checkpoint.required_input_schema,
        "prompt_payload": prompt_payload_summary(prompt_payload),
        "state_snapshot": state_snapshot_summary(state_snapshot),
        "created_at": checkpoint.created_at,
        "updated_at": checkpoint.updated_at,
        "consumed_at": checkpoint.consumed_at,
    }


def status_for_verification_report(verification_report: dict[str, Any] | None) -> str:
    if not isinstance(verification_report, dict):
        return "completed"
    status = str(verification_report.get("status") or "").casefold()
    if status == "failed":
        return "verification_failed"
    if status == "warning":
        return "completed_with_warnings"
    return "completed"


def collect_evidence_refs_from_events(events) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for event in events:
        raw_refs = (event.payload or {}).get("evidence_refs") or []
        for raw_ref in raw_refs:
            parsed = _parse_evidence_ref(raw_ref)
            if parsed is not None:
                refs.append(parsed)
    return refs


def graph_run_to_view(
    episode: AgentEpisode,
    checkpoint: dict[str, Any] | None,
    prompt_executions,
) -> dict[str, Any]:
    snapshot = episode.context_snapshot if isinstance(episode.context_snapshot, dict) else {}
    langfuse_trace_id = next(
        (
            execution.langfuse_trace_id
            for execution in prompt_executions
            if execution.langfuse_trace_id
        ),
        None,
    )
    return {
        "episode_id": str(episode.id),
        "learner_id": str(episode.learner_id),
        "thread_id": snapshot.get("thread_id") or (checkpoint or {}).get("thread_id"),
        "graph_run_id": snapshot.get("graph_run_id"),
        "session_id": snapshot.get("session_id"),
        "checkpoint_status": (checkpoint or {}).get("status") or snapshot.get("checkpoint_status"),
        "resume_from": (checkpoint or {}).get("resume_from") or snapshot.get("resume_from"),
        "current_task_id": (checkpoint or {}).get("current_task_id") or snapshot.get("current_task_id"),
        "answer_required": bool((checkpoint or {}).get("answer_required") or snapshot.get("answer_required")),
        "langfuse_trace_id": langfuse_trace_id,
    }


def node_summaries_from_trace(events, tool_calls, prompt_executions) -> list[dict[str, Any]]:
    event_counts = Counter(event.source_module for event in events)
    tool_counts = Counter(tool.tool_name for tool in tool_calls)
    prompt_counts = Counter(prompt.source_module for prompt in prompt_executions)
    names = sorted(set(event_counts) | set(tool_counts) | set(prompt_counts))
    return [
        {
            "node": name,
            "event_count": event_counts.get(name, 0),
            "tool_call_count": tool_counts.get(name, 0),
            "prompt_execution_count": prompt_counts.get(name, 0),
        }
        for name in names
    ]


def prompt_payload_summary(prompt_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not prompt_payload:
        return None
    prompt = prompt_payload.get("prompt")
    input_materials = prompt_payload.get("input_materials")
    return {
        "task_id": prompt_payload.get("task_id"),
        "prompt_preview": _preview(prompt),
        "prompt_chars": len(str(prompt)) if prompt is not None else 0,
        "input_material_count": len(input_materials) if isinstance(input_materials, list) else 0,
        "keys": sorted(str(key) for key in prompt_payload.keys()),
    }


def state_snapshot_summary(state_snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state_snapshot:
        return None
    return {
        "keys": sorted(str(key) for key in state_snapshot.keys()),
        "current_task_id": state_snapshot.get("current_task_id"),
        "answer_required": bool(state_snapshot.get("answer_required")),
        "resume_from": state_snapshot.get("resume_from"),
        "graph_run_id": state_snapshot.get("graph_run_id"),
        "thread_id": state_snapshot.get("thread_id"),
        "input_material_count": len(state_snapshot.get("input_materials") or []),
        "has_learner_answer": bool(state_snapshot.get("learner_answer")),
    }


def graph_run_debug_payload(trace: EpisodeTraceView) -> dict[str, Any]:
    graph_run = trace.graph_run or {}
    return {
        "episode_id": trace.episode.id,
        "learner_id": trace.episode.learner_id,
        "thread_id": graph_run.get("thread_id"),
        "graph_run_id": graph_run.get("graph_run_id"),
        "session_id": graph_run.get("session_id"),
        "checkpoint_status": graph_run.get("checkpoint_status"),
        "resume_from": graph_run.get("resume_from"),
        "current_task_id": graph_run.get("current_task_id"),
        "node_summaries": trace.node_summaries,
        "events": trace.events,
        "tool_calls": trace.tool_calls,
        "prompt_executions": trace.prompt_executions,
        "verification_report": trace.verification_report,
        "evidence_refs": trace.evidence_refs,
        "langfuse_trace_id": graph_run.get("langfuse_trace_id"),
        "trace": trace,
    }


def _parse_evidence_ref(raw_ref: Any) -> EvidenceRef | None:
    if isinstance(raw_ref, EvidenceRef):
        return raw_ref
    if not isinstance(raw_ref, dict):
        return None
    normalized = dict(raw_ref)
    if "evidence_type" not in normalized and "type" in normalized:
        normalized["evidence_type"] = normalized["type"]
    if "evidence_id" not in normalized and "id" in normalized:
        normalized["evidence_id"] = normalized["id"]
    if "evidence_type" not in normalized or "evidence_id" not in normalized:
        return None
    metadata = normalized.get("metadata")
    normalized["metadata"] = metadata if isinstance(metadata, dict) else {}
    try:
        return EvidenceRef(**normalized)
    except ValueError:
        return None


def _preview(value: Any, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
