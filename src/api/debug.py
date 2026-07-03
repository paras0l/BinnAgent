import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db_session, require_debug_access
from src.config import settings
from src.knowledge.review_queue import (
    mark_target_reviewed,
    recalculate_quality_gate_from_queue,
    queue_summary,
)
from src.knowledge.rag import retrieve_chunks
from src.models.knowledge import (
    CurriculumNode,
    ExerciseAttempt,
    ExerciseQuestion,
    KnowledgeChunk,
    KnowledgePoint,
    KnowledgeSource,
    ParserReviewItem,
    ParserRun,
)
from src.models.learner import Learner, LearnerProfile
from src.models.memory import LearningMemoryEvent
from src.models.prompt_execution import PromptExecutionRecord
from src.models.runtime import AgentEpisode
from src.models.vocabulary import VocabularyItem
from src.providers.router import router as model_router
from src.runtime.episode import EpisodeRuntime, graph_run_debug_payload
from src.security.ownership import CurrentUser, get_episode_for_user, get_learner_for_user
from src.simulation.fixtures import BUILTIN_SCENARIOS

router = APIRouter(
    prefix="/api/debug",
    tags=["debug"],
    dependencies=[Depends(require_debug_access)],
)

SIMULATION_REPORT_ROOT = Path("var/simulation")


@router.get("/learners")
async def list_debug_learners(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    ownership_filters = [
        Learner.tenant_id == current_user.user_id,
        Learner.id == current_user.user_id,
    ]
    if current_user.allow_unclaimed_learners:
        ownership_filters.append(Learner.tenant_id.is_(None))

    filters = [or_(*ownership_filters)]
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Learner.nickname.ilike(pattern), Learner.email.ilike(pattern)))

    episode_counts = (
        select(
            AgentEpisode.learner_id.label("learner_id"),
            func.count(AgentEpisode.id).label("episode_count"),
        )
        .group_by(AgentEpisode.learner_id)
        .subquery()
    )
    memory_counts = (
        select(
            LearningMemoryEvent.learner_id.label("learner_id"),
            func.count(LearningMemoryEvent.id).label("memory_event_count"),
        )
        .group_by(LearningMemoryEvent.learner_id)
        .subquery()
    )
    exercise_counts = (
        select(
            ExerciseAttempt.learner_id.label("learner_id"),
            func.count(ExerciseAttempt.id).label("exercise_attempt_count"),
        )
        .group_by(ExerciseAttempt.learner_id)
        .subquery()
    )
    vocabulary_counts = (
        select(
            VocabularyItem.learner_id.label("learner_id"),
            func.count(VocabularyItem.id).label("vocabulary_count"),
        )
        .group_by(VocabularyItem.learner_id)
        .subquery()
    )

    total_result = await db.execute(select(func.count()).select_from(Learner).where(*filters))
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(
            Learner,
            LearnerProfile,
            func.coalesce(episode_counts.c.episode_count, 0).label("episode_count"),
            func.coalesce(memory_counts.c.memory_event_count, 0).label("memory_event_count"),
            func.coalesce(exercise_counts.c.exercise_attempt_count, 0).label("exercise_attempt_count"),
            func.coalesce(vocabulary_counts.c.vocabulary_count, 0).label("vocabulary_count"),
        )
        .outerjoin(LearnerProfile, LearnerProfile.learner_id == Learner.id)
        .outerjoin(episode_counts, episode_counts.c.learner_id == Learner.id)
        .outerjoin(memory_counts, memory_counts.c.learner_id == Learner.id)
        .outerjoin(exercise_counts, exercise_counts.c.learner_id == Learner.id)
        .outerjoin(vocabulary_counts, vocabulary_counts.c.learner_id == Learner.id)
        .where(*filters)
        .order_by(Learner.updated_at.desc(), Learner.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    learners = [
        _debug_learner_summary(
            learner,
            profile,
            episode_count,
            memory_event_count,
            exercise_attempt_count,
            vocabulary_count,
        )
        for learner, profile, episode_count, memory_event_count, exercise_attempt_count, vocabulary_count
        in result.all()
    ]
    return {
        "learners": learners,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/rag/search")
async def search_rag_chunks(
    query: str = Query(..., min_length=1, max_length=500),
    learner_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    node_id: uuid.UUID | None = None,
    limit: int = Query(default=8, ge=1, le=30),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if learner_id is not None:
        await get_learner_for_user(
            db,
            current_user.user_id,
            learner_id,
            allow_unclaimed_learners=current_user.allow_unclaimed_learners,
        )
    chunks = await retrieve_chunks(
        db,
        model_router,
        query=query,
        source_id=source_id,
        curriculum_node_id=node_id,
        limit=limit,
    )
    retrieval_mode = chunks[0].retrieval_mode if chunks else "fallback"
    embedding_model = (
        chunks[0].embedding_model
        if chunks and chunks[0].embedding_model
        else settings.ollama_embedding_model
    )
    chunk_version = chunks[0].chunk_version if chunks else None
    return {
        "query": query,
        "learner_id": str(learner_id) if learner_id else None,
        "source_id": str(source_id) if source_id else None,
        "node_id": str(node_id) if node_id else None,
        "retrieval_mode": retrieval_mode,
        "embedding_model": embedding_model,
        "chunk_version": chunk_version,
        "result_count": len(chunks),
        "results": [
            {
                "chunk_id": str(chunk.chunk_id),
                "source_id": str(chunk.source_id),
                "curriculum_node_id": str(chunk.curriculum_node_id)
                if chunk.curriculum_node_id
                else None,
                "page_number": chunk.page_number,
                "score": chunk.score,
                "retrieval_mode": chunk.retrieval_mode,
                "content_preview": chunk.content[:500],
                "metadata": {
                    "embedding_model": chunk.embedding_model,
                    "chunk_version": chunk.chunk_version,
                    "source_version": chunk.source_version,
                },
            }
            for chunk in chunks
        ],
    }


@router.get("/textbook-sources")
async def list_debug_textbook_sources(
    status: str | None = Query(default=None, max_length=40),
    quality_status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    filters = _textbook_source_filters(status=status, quality_status=quality_status)
    total_result = await db.execute(
        select(func.count()).select_from(KnowledgeSource).where(*filters)
    )
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(KnowledgeSource)
        .where(*filters)
        .order_by(KnowledgeSource.updated_at.desc(), KnowledgeSource.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sources = list(result.scalars().all())
    source_ids = [source.id for source in sources]
    parser_runs_by_source = await _latest_parser_runs_by_source(db, source_ids)
    review_items_by_source = await _review_items_by_source(db, source_ids)
    return {
        "sources": [
            _textbook_source_debug_summary(
                source,
                latest_run=parser_runs_by_source.get(source.id),
                review_items=review_items_by_source.get(source.id, []),
            )
            for source in sources
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/textbook-sources/{source_id}/parsing-report")
async def get_debug_textbook_parsing_report(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_debug_source(db, source_id)
    latest_run = await _load_latest_parser_run(db, source)
    quality_report = _quality_report_payload(source, latest_run)
    quality_score = _quality_score_payload(source, latest_run)
    review_items = await _load_source_review_items(db, source_id)
    pending_review_items = [item for item in review_items if item.decision == "pending"]
    summary = queue_summary(review_items)
    return {
        "source": _textbook_source_debug_summary(
            source,
            latest_run=latest_run,
            review_items=review_items,
        ),
        "latest_parser_run": _parser_run_summary(latest_run, review_items) if latest_run else None,
        "quality_score": quality_score or None,
        "quality_report": quality_report or None,
        "quality_metrics_by_group": _quality_metric_groups(quality_report),
        "blocking_reasons": _blocking_reasons(source, quality_score),
        "warnings": _quality_warnings(source, quality_report, quality_score),
        "pending_review_count": summary.pending_review_count,
        "pending_blocker_count": summary.pending_blocker_count,
        "review_warning_count": summary.review_warning_count,
        "review_summary_by_issue_type": _review_summary_by(
            pending_review_items,
            "issue_type",
        ),
        "review_summary_by_severity": _review_summary_by(
            pending_review_items,
            "severity",
        ),
        "parser_artifacts": _parser_artifact_summary(latest_run),
        "evidence_coverage": _evidence_coverage_summary(quality_report),
    }


@router.get("/textbook-sources/{source_id}/parser-runs")
async def list_debug_parser_runs(
    source_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_debug_source(db, source_id)
    result = await db.execute(
        select(ParserRun)
        .where(ParserRun.source_id == source_id)
        .order_by(ParserRun.started_at.desc(), ParserRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = list(result.scalars().all())
    review_items = await _load_source_review_items(db, source_id)
    return {
        "source": _source_quality_summary(source),
        "parser_runs": [_parser_run_summary(run, review_items) for run in runs],
        "limit": limit,
        "offset": offset,
    }


@router.get("/textbook-sources/{source_id}/parser-runs/{parser_run_id}")
async def get_debug_parser_run(
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_debug_source(db, source_id)
    parser_run = await _load_parser_run_for_source(db, source_id, parser_run_id)
    review_items = await _load_source_review_items(db, source_id, parser_run_id=parser_run_id)
    return {
        "source": _source_quality_summary(source),
        "parser_run": _parser_run_detail(parser_run, review_items),
        "quality_report": _dict_or_empty(parser_run.quality_report) or None,
        "quality_score": _dict_or_empty(parser_run.quality_score) or None,
        "artifact_refs": _dict_or_empty(parser_run.artifact_refs),
        "error_message": parser_run.error_message,
        "review_items": [_review_item_debug_payload(item) for item in review_items],
        "review_summary_by_issue_type": _review_summary_by(review_items, "issue_type"),
        "review_summary_by_severity": _review_summary_by(review_items, "severity"),
    }


@router.get("/textbook-sources/{source_id}/review-items")
async def list_debug_parser_review_items(
    source_id: uuid.UUID,
    decision: str | None = Query(default=None, max_length=30),
    severity: str | None = Query(default=None, max_length=30),
    issue_type: str | None = Query(default=None, max_length=80),
    target_type: str | None = Query(default=None, max_length=50),
    parser_run_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    source = await _load_debug_source(db, source_id)
    filters = _review_item_filters(
        source_id=source_id,
        decision=decision,
        severity=severity,
        issue_type=issue_type,
        target_type=target_type,
        parser_run_id=parser_run_id,
    )
    result = await db.execute(
        select(ParserReviewItem)
        .where(*filters)
        .order_by(ParserReviewItem.severity.asc(), ParserReviewItem.created_at.asc())
    )
    items = list(result.scalars().all())
    all_items = await _load_source_review_items(db, source_id)
    summary = queue_summary(all_items)
    return {
        "source": _source_quality_summary(source),
        "source_quality_summary": _source_quality_summary(source),
        "summary": _queue_summary_payload(summary),
        "items": [_review_item_debug_payload(item) for item in items],
    }


@router.post("/textbook-sources/{source_id}/review-items/{review_item_id}/confirm")
async def confirm_debug_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: dict[str, Any] | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_debug_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        action="confirmed",
        body=body or {},
        current_user=current_user,
        db=db,
    )


@router.post("/textbook-sources/{source_id}/review-items/{review_item_id}/update")
async def update_debug_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: dict[str, Any],
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_debug_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        action="updated",
        body=body,
        current_user=current_user,
        db=db,
    )


@router.post("/textbook-sources/{source_id}/review-items/{review_item_id}/ignore")
async def ignore_debug_parser_review_item(
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    body: dict[str, Any] | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await _decide_debug_review_item(
        source_id=source_id,
        review_item_id=review_item_id,
        action="ignored",
        body=body or {},
        current_user=current_user,
        db=db,
    )


@router.get("/textbook-sources/{source_id}/evidence")
async def get_debug_parser_evidence(
    source_id: uuid.UUID,
    target_type: str | None = Query(default=None, max_length=50),
    target_id: uuid.UUID | None = None,
    parser_run_id: uuid.UUID | None = None,
    issue_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
    excerpt_limit: int = Query(default=500, ge=60, le=500),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _load_debug_source(db, source_id)
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = []

    if target_id is not None and not target_type:
        raise HTTPException(status_code=400, detail="target_type is required when target_id is provided")

    if target_type and target_id:
        target = await _load_evidence_target(db, source_id, target_type, target_id)
        review_items = await _load_review_items_for_target(db, source_id, target_type, target_id)
        item = _evidence_from_target(
            target_type=target_type,
            target=target,
            review_items=review_items,
            excerpt_limit=excerpt_limit,
        )
        if _has_parser_evidence(item):
            evidence.append(item)
        else:
            warnings.append("No parser evidence found for target.")
    elif parser_run_id is not None:
        await _load_parser_run_for_source(db, source_id, parser_run_id)
        evidence.extend(
            await _evidence_for_parser_run(
                db,
                source_id=source_id,
                parser_run_id=parser_run_id,
                limit=limit,
                excerpt_limit=excerpt_limit,
            )
        )
        if not evidence:
            warnings.append("No parser evidence found for parser_run_id.")
    elif issue_type:
        filters = _review_item_filters(source_id=source_id, issue_type=issue_type)
        result = await db.execute(
            select(ParserReviewItem)
            .where(*filters)
            .order_by(ParserReviewItem.created_at.asc())
            .limit(limit)
        )
        evidence = [
            _evidence_from_review_item(item, excerpt_limit=excerpt_limit)
            for item in result.scalars().all()
        ]
        if not evidence:
            warnings.append("No parser evidence found for issue_type.")
    else:
        warnings.append("Provide target_type + target_id, parser_run_id, or issue_type to query evidence.")

    return {
        "source_id": str(source_id),
        "query": {
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "parser_run_id": str(parser_run_id) if parser_run_id else None,
            "issue_type": issue_type,
        },
        "evidence": evidence[:limit],
        "warnings": warnings,
        "limit": limit,
        "excerpt_limit": excerpt_limit,
    }


@router.get("/prompts/executions")
async def list_prompt_executions(
    prompt_id: str | None = Query(default=None, max_length=160),
    learner_id: uuid.UUID | None = None,
    episode_id: uuid.UUID | None = None,
    source_module: str | None = Query(default=None, max_length=120),
    decision: str | None = Query(default=None, max_length=30),
    schema_validation_status: str | None = Query(default=None, max_length=30),
    repair_used: bool | None = None,
    fallback_used: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    filters = _prompt_execution_filters(
        prompt_id=prompt_id,
        learner_id=learner_id,
        episode_id=episode_id,
        source_module=source_module,
        decision=decision,
        schema_validation_status=schema_validation_status,
        repair_used=repair_used,
        fallback_used=fallback_used,
    )
    total_result = await db.execute(
        select(func.count()).select_from(PromptExecutionRecord).where(*filters)
    )
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(PromptExecutionRecord)
        .where(*filters)
        .order_by(PromptExecutionRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    records = result.scalars().all()
    return {
        "executions": [_prompt_execution_response(record) for record in records],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/prompts/executions/{execution_id}")
async def get_prompt_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(
        select(PromptExecutionRecord).where(PromptExecutionRecord.id == execution_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Prompt execution record not found")
    return _prompt_execution_response(record)


@router.get("/graph-runs")
async def list_debug_graph_runs(
    learner_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if learner_id is None:
        raise HTTPException(status_code=400, detail="learner_id is required")
    await get_learner_for_user(
        db,
        current_user.user_id,
        learner_id,
        allow_unclaimed_learners=current_user.allow_unclaimed_learners,
    )
    total_result = await db.execute(
        select(func.count()).select_from(AgentEpisode).where(AgentEpisode.learner_id == learner_id)
    )
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(AgentEpisode)
        .where(AgentEpisode.learner_id == learner_id)
        .order_by(AgentEpisode.started_at.desc(), AgentEpisode.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    episodes = result.scalars().all()
    return {
        "graph_runs": [_graph_run_summary(episode) for episode in episodes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/graph-runs/{episode_id}")
async def get_debug_graph_run(
    episode_id: uuid.UUID,
    learner_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    episode = await get_episode_for_user(db, current_user, episode_id)
    if learner_id is not None and episode.learner_id != learner_id:
        raise HTTPException(status_code=403, detail="Episode does not belong to learner_id")
    trace = await EpisodeRuntime(db).get_episode_trace(episode.id)
    return graph_run_debug_payload(trace)


@router.get("/simulation/scenarios")
async def list_simulation_scenarios() -> dict[str, Any]:
    return {
        "scenarios": [
            {
                "id": scenario.id,
                "name": scenario.name,
                "persona_id": scenario.persona_id,
                "step_count": len(scenario.steps),
                "steps": [
                    {
                        "name": step.name,
                        "action": step.action,
                        "assertion_count": len(step.assertions),
                    }
                    for step in scenario.steps
                ],
            }
            for scenario in BUILTIN_SCENARIOS.values()
        ]
    }


def _debug_learner_summary(
    learner: Learner,
    profile: LearnerProfile | None,
    episode_count: int,
    memory_event_count: int,
    exercise_attempt_count: int,
    vocabulary_count: int,
) -> dict[str, Any]:
    return {
        "id": str(learner.id),
        "nickname": learner.nickname,
        "email": learner.email,
        "created_at": learner.created_at,
        "updated_at": learner.updated_at,
        "profile": {
            "target_exam": profile.target_exam,
            "current_level": profile.current_level,
            "daily_time_budget_minutes": profile.daily_time_budget_minutes,
        }
        if profile
        else None,
        "counts": {
            "episode_count": int(episode_count or 0),
            "memory_event_count": int(memory_event_count or 0),
            "exercise_attempt_count": int(exercise_attempt_count or 0),
            "vocabulary_count": int(vocabulary_count or 0),
        },
    }


def _textbook_source_filters(
    *,
    status: str | None,
    quality_status: str | None,
) -> list[Any]:
    filters: list[Any] = []
    if status:
        filters.append(KnowledgeSource.status == status)
    if quality_status:
        filters.append(
            or_(
                KnowledgeSource.status == quality_status,
                KnowledgeSource.metadata_["quality_status"].as_string() == quality_status,
            )
        )
    return filters


async def _load_debug_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Textbook source not found")
    return source


async def _latest_parser_runs_by_source(
    db: AsyncSession,
    source_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ParserRun]:
    if not source_ids:
        return {}
    result = await db.execute(
        select(ParserRun)
        .where(ParserRun.source_id.in_(source_ids))
        .order_by(ParserRun.source_id.asc(), ParserRun.started_at.desc())
    )
    runs_by_source: dict[uuid.UUID, ParserRun] = {}
    for run in result.scalars().all():
        runs_by_source.setdefault(run.source_id, run)
    return runs_by_source


async def _review_items_by_source(
    db: AsyncSession,
    source_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[ParserReviewItem]]:
    if not source_ids:
        return {}
    result = await db.execute(
        select(ParserReviewItem).where(ParserReviewItem.source_id.in_(source_ids))
    )
    items_by_source: dict[uuid.UUID, list[ParserReviewItem]] = {}
    for item in result.scalars().all():
        items_by_source.setdefault(item.source_id, []).append(item)
    return items_by_source


async def _load_latest_parser_run(
    db: AsyncSession,
    source: KnowledgeSource,
) -> ParserRun | None:
    metadata = source.metadata_ or {}
    latest_run_id = _uuid_or_none(metadata.get("latest_parser_run_id"))
    if latest_run_id is not None:
        result = await db.execute(
            select(ParserRun).where(
                ParserRun.id == latest_run_id,
                ParserRun.source_id == source.id,
            )
        )
        run = result.scalar_one_or_none()
        if run is not None:
            return run
    result = await db.execute(
        select(ParserRun)
        .where(ParserRun.source_id == source.id)
        .order_by(ParserRun.started_at.desc(), ParserRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_parser_run_for_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID,
) -> ParserRun:
    result = await db.execute(
        select(ParserRun).where(
            ParserRun.id == parser_run_id,
            ParserRun.source_id == source_id,
        )
    )
    parser_run = result.scalar_one_or_none()
    if parser_run is None:
        raise HTTPException(status_code=404, detail="Parser run not found for source")
    return parser_run


async def _load_source_review_items(
    db: AsyncSession,
    source_id: uuid.UUID,
    *,
    parser_run_id: uuid.UUID | None = None,
) -> list[ParserReviewItem]:
    filters = [ParserReviewItem.source_id == source_id]
    if parser_run_id is not None:
        filters.append(ParserReviewItem.parser_run_id == parser_run_id)
    result = await db.execute(
        select(ParserReviewItem)
        .where(*filters)
        .order_by(ParserReviewItem.created_at.asc())
    )
    return list(result.scalars().all())


def _textbook_source_debug_summary(
    source: KnowledgeSource,
    *,
    latest_run: ParserRun | None,
    review_items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    quality_score = _quality_score_payload(source, latest_run)
    pending_items = [item for item in review_items if item.decision == "pending"]
    latest_parser_run_id = (
        str(latest_run.id)
        if latest_run
        else metadata.get("latest_parser_run_id")
    )
    return {
        "source_id": str(source.id),
        "id": str(source.id),
        "title": source.title,
        "name": source.title,
        "filename": source.filename,
        "status": source.status,
        "quality_status": _quality_status(source, quality_score),
        "overall_score": _overall_score(quality_score),
        "parser_status": metadata.get("parser_status") or (latest_run.status if latest_run else None),
        "latest_parser_run_id": latest_parser_run_id,
        "latest_parser_version": latest_run.parser_version if latest_run else None,
        "pending_review_count": len(pending_items)
        if review_items
        else int(metadata.get("pending_review_count") or 0),
        "pending_blocker_count": sum(1 for item in pending_items if item.severity == "blocker")
        if review_items
        else int(metadata.get("pending_blocker_count") or 0),
        "review_warning_count": sum(1 for item in pending_items if item.severity == "warning")
        if review_items
        else int(metadata.get("review_warning_count") or 0),
        "blocking_reasons": _blocking_reasons(source, quality_score),
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _source_quality_summary(source: KnowledgeSource) -> dict[str, Any]:
    metadata = source.metadata_ or {}
    quality_score = _quality_score_payload(source, None)
    return {
        "source_id": str(source.id),
        "title": source.title,
        "status": source.status,
        "quality_status": _quality_status(source, quality_score),
        "overall_score": _overall_score(quality_score),
        "parser_status": metadata.get("parser_status"),
        "latest_parser_run_id": metadata.get("latest_parser_run_id"),
        "pending_review_count": int(metadata.get("pending_review_count") or 0),
        "pending_blocker_count": int(metadata.get("pending_blocker_count") or 0),
        "review_warning_count": int(metadata.get("review_warning_count") or 0),
        "blocking_reasons": _blocking_reasons(source, quality_score),
    }


def _quality_score_payload(
    source: KnowledgeSource,
    parser_run: ParserRun | None,
) -> dict[str, Any]:
    if parser_run is not None and isinstance(parser_run.quality_score, dict):
        return dict(parser_run.quality_score)
    metadata = source.metadata_ or {}
    if isinstance(metadata.get("quality_score"), dict):
        return dict(metadata["quality_score"])
    return {}


def _quality_report_payload(
    source: KnowledgeSource,
    parser_run: ParserRun | None,
) -> dict[str, Any]:
    if parser_run is not None and isinstance(parser_run.quality_report, dict):
        return dict(parser_run.quality_report)
    metadata = source.metadata_ or {}
    if isinstance(metadata.get("parser_report"), dict):
        return dict(metadata["parser_report"])
    return {}


def _quality_status(source: KnowledgeSource, quality_score: dict[str, Any]) -> str:
    metadata = source.metadata_ or {}
    return str(
        quality_score.get("status")
        or metadata.get("quality_status")
        or source.status
    )


def _overall_score(quality_score: dict[str, Any]) -> float | None:
    value = quality_score.get("overall_score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _blocking_reasons(
    source: KnowledgeSource,
    quality_score: dict[str, Any],
) -> list[str]:
    metadata = source.metadata_ or {}
    reasons = quality_score.get("blocking_reasons") or metadata.get("blocking_reasons") or []
    if not isinstance(reasons, list):
        return [str(reasons)]
    return [str(reason) for reason in reasons]


def _quality_warnings(
    source: KnowledgeSource,
    quality_report: dict[str, Any],
    quality_score: dict[str, Any],
) -> list[str]:
    metadata = source.metadata_ or {}
    warnings: list[str] = []
    for value in (
        quality_score.get("warnings"),
        quality_report.get("warnings"),
        [metadata.get("warning")] if metadata.get("warning") else None,
    ):
        if not isinstance(value, list):
            continue
        warnings.extend(str(item) for item in value if item)
    return _dedupe_strings(warnings)


def _quality_metric_groups(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "intake": _pick_report_metrics(
            report,
            [
                "page_count",
                "text_char_count",
                "avg_text_chars_per_page",
                "empty_page_ratio",
                "has_text_layer",
                "is_scanned_pdf_suspected",
            ],
        ),
        "structure": _pick_report_metrics(
            report,
            [
                "unit_count",
                "expected_unit_count",
                "unit_title_match_rate",
                "unit_order_valid",
                "section_count",
                "section_coverage_rate",
            ],
        ),
        "vocabulary": _pick_report_metrics(
            report,
            [
                "vocabulary_entry_count",
                "expected_min_vocabulary_count",
                "core_vocabulary_hit_rate",
                "low_confidence_vocabulary_ratio",
                "dirty_token_entry_count",
            ],
        ),
        "knowledge": _pick_report_metrics(
            report,
            [
                "knowledge_count_by_type",
                "source_page_coverage_rate",
                "evidence_ref_coverage_rate",
                "duplicate_knowledge_count",
                "requires_review_count",
            ],
        ),
        "rag": _pick_report_metrics(
            report,
            [
                "rag_chunk_count",
                "rag_page_coverage_rate",
                "chunk_avg_size",
            ],
        ),
    }


def _pick_report_metrics(report: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: report.get(key) for key in keys}


def _evidence_coverage_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_page_coverage_rate": report.get("source_page_coverage_rate"),
        "evidence_ref_coverage_rate": report.get("evidence_ref_coverage_rate"),
        "rag_page_coverage_rate": report.get("rag_page_coverage_rate"),
        "requires_review_count": report.get("requires_review_count"),
        "pending_blocker_count": report.get("pending_blocker_count"),
        "review_warning_count": report.get("review_warning_count"),
    }


def _parser_artifact_summary(parser_run: ParserRun | None) -> dict[str, Any]:
    if parser_run is None:
        return {}
    artifacts = _dict_or_empty(parser_run.artifact_refs)
    return {
        "artifact_refs": artifacts,
        "curriculum_node_count": artifacts.get("curriculum_node_count"),
        "knowledge_point_count": artifacts.get("knowledge_point_count"),
        "rag_chunk_count": artifacts.get("rag_chunk_count"),
        "review_item_count": artifacts.get("review_item_count"),
    }


def _parser_run_summary(
    parser_run: ParserRun,
    review_items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
) -> dict[str, Any]:
    related_items = [
        item for item in review_items if item.parser_run_id == parser_run.id
    ]
    quality_score = _dict_or_empty(parser_run.quality_score)
    return {
        "parser_run_id": str(parser_run.id),
        "parser_id": parser_run.parser_id,
        "parser_version": parser_run.parser_version,
        "status": parser_run.status,
        "started_at": parser_run.started_at,
        "completed_at": parser_run.completed_at,
        "duration_ms": _duration_ms(parser_run.started_at, parser_run.completed_at),
        "quality_status": quality_score.get("status"),
        "overall_score": _overall_score(quality_score),
        "pending_review_count": sum(
            1 for item in related_items if item.decision == "pending"
        ),
        "error_message": _truncate_text(parser_run.error_message, 300),
    }


def _parser_run_detail(
    parser_run: ParserRun,
    review_items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
) -> dict[str, Any]:
    payload = _parser_run_summary(parser_run, review_items)
    payload.update(
        {
            "source_id": str(parser_run.source_id),
            "parser_profile_id": parser_run.parser_profile_id,
            "book_manifest_id": parser_run.book_manifest_id,
            "pdf_sha256": parser_run.pdf_sha256,
            "input_hash": parser_run.input_hash,
            "quality_report": _dict_or_empty(parser_run.quality_report) or None,
            "quality_score": _dict_or_empty(parser_run.quality_score) or None,
            "artifact_refs": _dict_or_empty(parser_run.artifact_refs),
            "error_message": parser_run.error_message,
            "created_at": parser_run.created_at,
            "updated_at": parser_run.updated_at,
        }
    )
    return payload


def _review_item_filters(
    *,
    source_id: uuid.UUID,
    decision: str | None = None,
    severity: str | None = None,
    issue_type: str | None = None,
    target_type: str | None = None,
    parser_run_id: uuid.UUID | None = None,
) -> list[Any]:
    filters: list[Any] = [ParserReviewItem.source_id == source_id]
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
    return filters


def _review_item_debug_payload(item: ParserReviewItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "source_id": str(item.source_id),
        "parser_run_id": str(item.parser_run_id) if item.parser_run_id else None,
        "issue_type": item.issue_type,
        "severity": item.severity,
        "decision": item.decision,
        "target_type": item.target_type,
        "target_id": str(item.target_id) if item.target_id else None,
        "evidence_snapshot": item.evidence_snapshot or {},
        "suggested_fix": item.suggested_fix or {},
        "review_note": item.review_note,
        "reviewed_at": item.reviewed_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _review_summary_by(
    items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
    field: str,
) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in items:
        value = str(getattr(item, field) or "unknown")
        summary[value] = summary.get(value, 0) + 1
    return summary


def _queue_summary_payload(summary: Any) -> dict[str, int]:
    return {
        "pending_review_count": int(summary.pending_review_count),
        "pending_blocker_count": int(summary.pending_blocker_count),
        "review_warning_count": int(summary.review_warning_count),
    }


async def _load_debug_review_item(
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


async def _decide_debug_review_item(
    *,
    source_id: uuid.UUID,
    review_item_id: uuid.UUID,
    action: str,
    body: dict[str, Any],
    current_user: CurrentUser,
    db: AsyncSession,
) -> dict[str, Any]:
    source = await _load_debug_source(db, source_id)
    item = await _load_debug_review_item(db, source_id, review_item_id)
    if item.decision != "pending":
        raise HTTPException(status_code=409, detail="Review item has already been decided")

    review_note = _optional_str(body.get("review_note"))
    allow_blocker_ignore = bool(body.get("allow_blocker_ignore"))
    if action == "ignored" and item.severity == "blocker" and not allow_blocker_ignore:
        raise HTTPException(
            status_code=409,
            detail="Blocker review item requires allow_blocker_ignore=true and review_note.",
        )
    if action == "ignored" and item.severity == "blocker" and not review_note:
        raise HTTPException(
            status_code=422,
            detail="Ignoring a blocker requires review_note.",
        )

    target = await _load_debug_review_target(db, item)
    if action == "updated":
        patch = body.get("patch") if isinstance(body.get("patch"), dict) else None
        _apply_debug_review_patch(target, patch)
    if action in {"confirmed", "updated"} or item.severity in {"warning", "info"} or allow_blocker_ignore:
        mark_target_reviewed(
            target,
            decision=action,
            learner_id=current_user.user_id,
            note=review_note,
        )

    item.decision = action
    item.review_note = review_note
    item.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    summary = await recalculate_quality_gate_from_queue(db, source)
    return {
        "source": _source_quality_summary(source),
        "source_quality_summary": _source_quality_summary(source),
        "summary": _queue_summary_payload(summary),
        "item": _review_item_debug_payload(item),
    }


async def _load_debug_review_target(
    db: AsyncSession,
    item: ParserReviewItem,
) -> Any | None:
    if item.target_id is None:
        return None
    model = _target_model(item.target_type)
    if model is None:
        return None
    result = await db.execute(
        select(model).where(
            model.id == item.target_id,
            model.source_id == item.source_id,
        )
    )
    return result.scalar_one_or_none()


def _apply_debug_review_patch(target: Any | None, patch: dict[str, Any] | None) -> None:
    if target is None or not patch:
        return
    if isinstance(target, KnowledgePoint):
        _apply_allowed_debug_attrs(target, patch, {"title", "summary", "source_page", "difficulty"})
        content_patch = patch.get("content")
        if isinstance(content_patch, dict):
            content = dict(target.content or {})
            for key in {
                "text",
                "source_page",
                "confidence",
                "warnings",
                "raw_line",
                "raw_text_excerpt",
                "raw_text_span",
                "evidence_refs",
                "evidence_pdf_pages",
                "lemma",
                "origin",
                "schema_version",
            }:
                if key in content_patch:
                    content[key] = content_patch[key]
            if "source_page" in content_patch:
                target.source_page = str(content_patch["source_page"])
            target.content = content
    elif isinstance(target, ExerciseQuestion):
        _apply_allowed_debug_attrs(
            target,
            patch,
            {"stem", "options", "answer", "explanation", "difficulty"},
        )
        metadata_patch = patch.get("metadata") or patch.get("content")
        if isinstance(metadata_patch, dict):
            metadata = dict(target.metadata_ or {})
            for key in {
                "source_page",
                "confidence",
                "warnings",
                "evidence_refs",
                "parser_run_id",
                "origin",
                "raw_line",
                "raw_text_excerpt",
                "raw_text_span",
                "schema_version",
            }:
                if key in metadata_patch:
                    metadata[key] = metadata_patch[key]
            target.metadata_ = metadata
    elif isinstance(target, KnowledgeChunk):
        _apply_allowed_debug_attrs(target, patch, {"content", "page_number"})
        metadata_patch = patch.get("metadata") or patch.get("content")
        if isinstance(metadata_patch, dict):
            metadata = dict(target.metadata_ or {})
            for key in {
                "source_page",
                "confidence",
                "warnings",
                "parser_run_id",
                "origin",
                "raw_text_span",
                "schema_version",
            }:
                if key in metadata_patch:
                    metadata[key] = metadata_patch[key]
            target.metadata_ = metadata
    elif isinstance(target, CurriculumNode):
        _apply_allowed_debug_attrs(
            target,
            patch,
            {"title", "subtitle", "start_page", "end_page", "learning_objectives"},
        )


def _apply_allowed_debug_attrs(target: Any, patch: dict[str, Any], allowed: set[str]) -> None:
    for key in allowed:
        if key in patch:
            setattr(target, key, patch[key])


async def _load_evidence_target(
    db: AsyncSession,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> Any:
    model = _target_model(target_type)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unsupported target_type: {target_type}")
    result = await db.execute(
        select(model).where(
            model.id == target_id,
            model.source_id == source_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found in source")
    return target


async def _load_review_items_for_target(
    db: AsyncSession,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> list[ParserReviewItem]:
    result = await db.execute(
        select(ParserReviewItem).where(
            ParserReviewItem.source_id == source_id,
            ParserReviewItem.target_type == target_type,
            ParserReviewItem.target_id == target_id,
        )
    )
    return list(result.scalars().all())


def _target_model(target_type: str) -> Any | None:
    return {
        "knowledge_point": KnowledgePoint,
        "curriculum_node": CurriculumNode,
        "exercise_question": ExerciseQuestion,
        "knowledge_chunk": KnowledgeChunk,
    }.get(target_type)


async def _evidence_for_parser_run(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    parser_run_id: uuid.UUID,
    limit: int,
    excerpt_limit: int,
) -> list[dict[str, Any]]:
    parser_run_id_str = str(parser_run_id)
    review_result = await db.execute(
        select(ParserReviewItem).where(
            ParserReviewItem.source_id == source_id,
            ParserReviewItem.parser_run_id == parser_run_id,
        )
    )
    review_items_by_target: dict[tuple[str, uuid.UUID | None], list[ParserReviewItem]] = {}
    for item in review_result.scalars().all():
        review_items_by_target.setdefault((item.target_type, item.target_id), []).append(item)

    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.source_id == source_id,
            KnowledgePoint.content["parser_run_id"].as_string() == parser_run_id_str,
        )
        .limit(limit)
    )
    chunk_result = await db.execute(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.source_id == source_id,
            KnowledgeChunk.metadata_["parser_run_id"].as_string() == parser_run_id_str,
        )
        .limit(limit)
    )
    exercise_result = await db.execute(
        select(ExerciseQuestion)
        .where(
            ExerciseQuestion.source_id == source_id,
            ExerciseQuestion.metadata_["parser_run_id"].as_string() == parser_run_id_str,
        )
        .limit(limit)
    )

    evidence: list[dict[str, Any]] = []
    for point in point_result.scalars().all():
        item = _evidence_from_target(
            target_type="knowledge_point",
            target=point,
            review_items=review_items_by_target.get(("knowledge_point", point.id), []),
            excerpt_limit=excerpt_limit,
        )
        if _has_parser_evidence(item):
            evidence.append(item)
    for chunk in chunk_result.scalars().all():
        item = _evidence_from_target(
            target_type="knowledge_chunk",
            target=chunk,
            review_items=review_items_by_target.get(("knowledge_chunk", chunk.id), []),
            excerpt_limit=excerpt_limit,
        )
        if _has_parser_evidence(item):
            evidence.append(item)
    for question in exercise_result.scalars().all():
        item = _evidence_from_target(
            target_type="exercise_question",
            target=question,
            review_items=review_items_by_target.get(("exercise_question", question.id), []),
            excerpt_limit=excerpt_limit,
        )
        if _has_parser_evidence(item):
            evidence.append(item)
    return evidence[:limit]


def _evidence_from_target(
    *,
    target_type: str,
    target: Any,
    review_items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
    excerpt_limit: int,
) -> dict[str, Any]:
    if isinstance(target, KnowledgePoint):
        content = dict(target.content or {})
        raw_line = _optional_str(content.get("raw_line"))
        return _evidence_payload(
            target_type=target_type,
            target_id=target.id,
            parser_run_id=content.get("parser_run_id"),
            origin=content.get("origin"),
            source_page=content.get("source_page") or target.source_page,
            pdf_page=_first_value(content.get("evidence_pdf_pages")),
            raw_line=raw_line,
            raw_text_excerpt=content.get("raw_text_excerpt") or raw_line,
            raw_text_span=content.get("raw_text_span"),
            confidence=content.get("confidence"),
            warnings=content.get("warnings"),
            schema_version=content.get("schema_version"),
            review_items=review_items,
            excerpt_limit=excerpt_limit,
        )
    if isinstance(target, CurriculumNode):
        return _evidence_payload(
            target_type=target_type,
            target_id=target.id,
            parser_run_id=None,
            origin=None,
            source_page=target.start_page,
            pdf_page=_int_or_none(target.start_page),
            raw_line=None,
            raw_text_excerpt=None,
            raw_text_span=None,
            confidence=None,
            warnings=[],
            schema_version=None,
            review_items=review_items,
            excerpt_limit=excerpt_limit,
        )
    if isinstance(target, ExerciseQuestion):
        metadata = dict(target.metadata_ or {})
        raw_line = _optional_str(metadata.get("raw_line"))
        return _evidence_payload(
            target_type=target_type,
            target_id=target.id,
            parser_run_id=metadata.get("parser_run_id"),
            origin=metadata.get("origin") or metadata.get("generated_by"),
            source_page=metadata.get("source_page"),
            pdf_page=_first_value(metadata.get("evidence_pdf_pages")),
            raw_line=raw_line,
            raw_text_excerpt=metadata.get("raw_text_excerpt") or raw_line or target.stem,
            raw_text_span=metadata.get("raw_text_span"),
            confidence=metadata.get("confidence"),
            warnings=metadata.get("warnings"),
            schema_version=metadata.get("schema_version"),
            review_items=review_items,
            excerpt_limit=excerpt_limit,
        )
    if isinstance(target, KnowledgeChunk):
        metadata = dict(target.metadata_ or {})
        return _evidence_payload(
            target_type=target_type,
            target_id=target.id,
            parser_run_id=metadata.get("parser_run_id"),
            origin=metadata.get("origin"),
            source_page=metadata.get("source_page") or str(target.page_number),
            pdf_page=target.page_number,
            raw_line=None,
            raw_text_excerpt=target.content,
            raw_text_span=metadata.get("raw_text_span"),
            confidence=metadata.get("confidence"),
            warnings=metadata.get("warnings"),
            schema_version=metadata.get("schema_version"),
            review_items=review_items,
            excerpt_limit=excerpt_limit,
        )
    raise HTTPException(status_code=400, detail=f"Unsupported target_type: {target_type}")


def _evidence_from_review_item(
    item: ParserReviewItem,
    *,
    excerpt_limit: int,
) -> dict[str, Any]:
    snapshot = item.evidence_snapshot or {}
    raw_line = _optional_str(snapshot.get("raw_line"))
    return _evidence_payload(
        target_type=item.target_type,
        target_id=item.target_id,
        parser_run_id=item.parser_run_id or snapshot.get("parser_run_id"),
        origin=snapshot.get("origin"),
        source_page=snapshot.get("source_page"),
        pdf_page=snapshot.get("pdf_page"),
        raw_line=raw_line,
        raw_text_excerpt=snapshot.get("raw_text_excerpt") or raw_line or snapshot.get("reason"),
        raw_text_span=snapshot.get("raw_text_span"),
        confidence=snapshot.get("confidence"),
        warnings=snapshot.get("warnings"),
        schema_version=snapshot.get("schema_version"),
        review_items=[item],
        excerpt_limit=excerpt_limit,
    )


def _evidence_payload(
    *,
    target_type: str,
    target_id: uuid.UUID | None,
    parser_run_id: Any,
    origin: Any,
    source_page: Any,
    pdf_page: Any,
    raw_line: str | None,
    raw_text_excerpt: Any,
    raw_text_span: Any,
    confidence: Any,
    warnings: Any,
    schema_version: Any,
    review_items: list[ParserReviewItem] | tuple[ParserReviewItem, ...],
    excerpt_limit: int,
) -> dict[str, Any]:
    return {
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "parser_run_id": _uuidish_to_str(parser_run_id),
        "origin": _optional_str(origin),
        "source_page": _optional_str(source_page),
        "pdf_page": _first_value(pdf_page),
        "raw_line": _truncate_text(raw_line, excerpt_limit),
        "raw_text_excerpt": _truncate_text(_optional_str(raw_text_excerpt), excerpt_limit),
        "raw_text_span": raw_text_span,
        "confidence": _float_or_none(confidence),
        "warnings": _string_list(warnings),
        "schema_version": _optional_str(schema_version),
        "review_item_ids": [str(item.id) for item in review_items],
        "issue_types": _dedupe_strings([item.issue_type for item in review_items]),
    }


def _has_parser_evidence(item: dict[str, Any]) -> bool:
    return any(
        item.get(key) not in (None, "", [])
        for key in (
            "parser_run_id",
            "origin",
            "source_page",
            "pdf_page",
            "raw_line",
            "raw_text_excerpt",
            "confidence",
            "warnings",
            "review_item_ids",
            "issue_types",
        )
    )


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if started_at is None or completed_at is None:
        return None
    return max(0, int((completed_at - started_at).total_seconds() * 1000))


def _truncate_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3]}..."


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _uuidish_to_str(value: Any) -> str | None:
    if isinstance(value, uuid.UUID):
        return str(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _first_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _prompt_execution_filters(
    *,
    prompt_id: str | None,
    learner_id: uuid.UUID | None,
    episode_id: uuid.UUID | None,
    source_module: str | None,
    decision: str | None,
    schema_validation_status: str | None,
    repair_used: bool | None,
    fallback_used: bool | None,
) -> list[Any]:
    filters: list[Any] = []
    if prompt_id:
        filters.append(PromptExecutionRecord.prompt_id == prompt_id)
    if learner_id is not None:
        filters.append(PromptExecutionRecord.learner_id == learner_id)
    if episode_id is not None:
        filters.append(PromptExecutionRecord.episode_id == episode_id)
    if source_module:
        filters.append(PromptExecutionRecord.source_module == source_module)
    if decision:
        filters.append(PromptExecutionRecord.decision == decision)
    if schema_validation_status:
        filters.append(PromptExecutionRecord.schema_validation_status == schema_validation_status)
    if repair_used is not None:
        filters.append(PromptExecutionRecord.repair_used.is_(repair_used))
    if fallback_used is not None:
        filters.append(PromptExecutionRecord.fallback_used.is_(fallback_used))
    return filters


def _prompt_execution_response(record: PromptExecutionRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "learner_id": str(record.learner_id) if record.learner_id else None,
        "episode_id": str(record.episode_id) if record.episode_id else None,
        "task_id": record.task_id,
        "source_module": record.source_module,
        "prompt_id": record.prompt_id,
        "prompt_version": record.prompt_version,
        "prompt_hash": record.prompt_hash,
        "input_hash": record.input_hash,
        "input_schema": record.input_schema,
        "output_schema": record.output_schema,
        "model_policy_snapshot": record.model_policy_snapshot or {},
        "langfuse_trace_id": record.langfuse_trace_id,
        "langfuse_observation_id": record.langfuse_observation_id,
        "schema_validation_status": record.schema_validation_status,
        "schema_error_summary": record.schema_error_summary,
        "repair_used": record.repair_used,
        "fallback_used": record.fallback_used,
        "parse_mode": record.parse_mode,
        "confidence": record.confidence,
        "decision": record.decision,
        "target_type": record.target_type,
        "target_id": record.target_id,
        "created_at": record.created_at,
    }


def _graph_run_summary(episode: AgentEpisode) -> dict[str, Any]:
    context_snapshot = (
        episode.context_snapshot if isinstance(episode.context_snapshot, dict) else {}
    )
    verification_report = (
        episode.verification_report if isinstance(episode.verification_report, dict) else {}
    )
    return {
        "episode_id": str(episode.id),
        "learner_id": str(episode.learner_id),
        "thread_id": context_snapshot.get("thread_id"),
        "graph_run_id": context_snapshot.get("graph_run_id"),
        "session_id": context_snapshot.get("session_id"),
        "checkpoint_status": context_snapshot.get("checkpoint_status"),
        "resume_from": context_snapshot.get("resume_from"),
        "current_task_id": context_snapshot.get("current_task_id"),
        "status": episode.status,
        "source": episode.source,
        "entrypoint": episode.entrypoint,
        "verification_status": verification_report.get("status"),
        "started_at": episode.started_at,
        "completed_at": episode.completed_at,
    }


@router.get("/simulation/reports/latest")
async def get_latest_simulation_report() -> dict[str, Any]:
    report_path = _latest_report_path()
    if report_path is None:
        raise HTTPException(status_code=404, detail="Simulation report not found")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Simulation report could not be read") from exc

    return {
        "path": str(report_path),
        "report": report,
        "summary": _simulation_report_summary(report),
    }


def _latest_report_path() -> Path | None:
    latest_path = SIMULATION_REPORT_ROOT / "latest_report.json"
    if latest_path.exists():
        return latest_path

    reports_dir = SIMULATION_REPORT_ROOT / "reports"
    if not reports_dir.exists():
        return None

    reports = [path for path in reports_dir.glob("*.json") if path.is_file()]
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def _simulation_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    steps = report.get("steps") if isinstance(report.get("steps"), list) else []
    step_dicts = [step for step in steps if isinstance(step, dict)]
    runtime_metrics = (
        report.get("runtime_metrics") if isinstance(report.get("runtime_metrics"), dict) else {}
    )
    failures = report.get("failures") if isinstance(report.get("failures"), list) else []
    failed_assertions = [
        failure
        for step in steps
        if isinstance(step, dict)
        for failure in step.get("failures", [])
    ]
    failed_assertions.extend(failures)
    return {
        "run_id": report.get("run_id"),
        "status": report.get("status", "unknown"),
        "episode_count": int(runtime_metrics.get("episode_count") or 0),
        "completed_episode_count": int(runtime_metrics.get("completed_episode_count") or 0),
        "failed_episode_count": int(runtime_metrics.get("failed_episode_count") or 0),
        "verification_pass_count": int(runtime_metrics.get("verification_pass_count") or 0),
        "verification_fail_count": int(runtime_metrics.get("verification_fail_count") or 0),
        "avg_tool_latency_ms": float(runtime_metrics.get("avg_tool_latency_ms") or 0),
        "failed_assertions": failed_assertions,
        "failed_assertion_count": len(failed_assertions),
        "step_count": len(step_dicts),
        "passed_step_count": sum(1 for step in step_dicts if step.get("status") == "passed"),
        "failed_step_count": sum(1 for step in step_dicts if step.get("status") == "failed"),
    }
