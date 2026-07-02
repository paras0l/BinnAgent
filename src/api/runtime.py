import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, require_debug_access
from src.models.learner import Learner
from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
from src.runtime.episode import EpisodeRuntime
from src.runtime.schemas import EpisodeTraceView
from src.verification.report import VerificationService
from src.verification.types import VerificationReport

router = APIRouter(
    prefix="/api/runtime",
    tags=["runtime"],
    dependencies=[Depends(require_debug_access)],
)


@router.get("/episodes")
async def list_runtime_episodes(
    learner_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, max_length=30),
    source: str | None = Query(default=None, max_length=80),
    entrypoint: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    filters = []
    if learner_id:
        filters.append(AgentEpisode.learner_id == learner_id)
    if status:
        filters.append(AgentEpisode.status == status)
    if source:
        filters.append(AgentEpisode.source == source)
    if entrypoint:
        filters.append(AgentEpisode.entrypoint == entrypoint)

    event_counts = (
        select(
            LearningEvent.episode_id.label("episode_id"),
            func.count(LearningEvent.id).label("event_count"),
        )
        .group_by(LearningEvent.episode_id)
        .subquery()
    )
    tool_counts = (
        select(
            ToolCallRecord.episode_id.label("episode_id"),
            func.count(ToolCallRecord.id).label("tool_call_count"),
        )
        .group_by(ToolCallRecord.episode_id)
        .subquery()
    )

    total_result = await db.execute(
        select(func.count()).select_from(AgentEpisode).where(*filters)
    )
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(
            AgentEpisode,
            Learner.nickname.label("learner_nickname"),
            func.coalesce(event_counts.c.event_count, 0).label("event_count"),
            func.coalesce(tool_counts.c.tool_call_count, 0).label("tool_call_count"),
        )
        .outerjoin(Learner, Learner.id == AgentEpisode.learner_id)
        .outerjoin(event_counts, event_counts.c.episode_id == AgentEpisode.id)
        .outerjoin(tool_counts, tool_counts.c.episode_id == AgentEpisode.id)
        .where(*filters)
        .order_by(AgentEpisode.started_at.desc(), AgentEpisode.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "episodes": [
            _episode_summary(episode, learner_nickname, event_count, tool_call_count)
            for episode, learner_nickname, event_count, tool_call_count in result.all()
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/episodes/{episode_id}", response_model=EpisodeTraceView)
async def get_runtime_episode(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> EpisodeTraceView:
    try:
        return await EpisodeRuntime(db).get_episode_trace(episode_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="AgentEpisode not found") from exc


def _episode_summary(
    episode: AgentEpisode,
    learner_nickname: str | None,
    event_count: int,
    tool_call_count: int,
) -> dict[str, Any]:
    task_spec = episode.task_spec if isinstance(episode.task_spec, dict) else {}
    target = task_spec.get("target") if isinstance(task_spec.get("target"), dict) else {}
    verification_report = (
        episode.verification_report if isinstance(episode.verification_report, dict) else {}
    )
    context_snapshot = (
        episode.context_snapshot if isinstance(episode.context_snapshot, dict) else {}
    )
    return {
        "id": str(episode.id),
        "learner_id": str(episode.learner_id),
        "learner_nickname": learner_nickname,
        "source": episode.source,
        "entrypoint": episode.entrypoint,
        "status": episode.status,
        "task_type": _optional_text(task_spec.get("task_type")),
        "task_objective": _optional_text(task_spec.get("objective")),
        "target_type": _optional_text(target.get("target_type") or target.get("type")),
        "target_id": _optional_text(target.get("target_id") or target.get("id")),
        "started_at": episode.started_at,
        "completed_at": episode.completed_at,
        "created_at": episode.created_at,
        "event_count": int(event_count or 0),
        "tool_call_count": int(tool_call_count or 0),
        "verification_status": _optional_text(verification_report.get("status")),
        "checkpoint_id": _optional_text(context_snapshot.get("checkpoint_id")),
        "checkpoint_status": _optional_text(context_snapshot.get("checkpoint_status")),
        "resume_from": _optional_text(context_snapshot.get("resume_from")),
        "answer_required": bool(context_snapshot.get("answer_required", False)),
        "failure_type": episode.failure_type,
        "error_message": episode.error_message,
    }


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@router.get("/episodes/{episode_id}/verification", response_model=VerificationReport)
async def get_runtime_episode_verification(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> VerificationReport:
    try:
        return await VerificationService(db).verify_episode(str(episode_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="AgentEpisode not found") from exc
