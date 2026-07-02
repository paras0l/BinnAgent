import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, require_debug_access
from src.config import settings
from src.knowledge.rag import retrieve_chunks
from src.models.knowledge import ExerciseAttempt
from src.models.learner import Learner, LearnerProfile
from src.models.memory import LearningMemoryEvent
from src.models.runtime import AgentEpisode
from src.models.vocabulary import VocabularyItem
from src.providers.router import router as model_router
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
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    filters = []
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
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
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
