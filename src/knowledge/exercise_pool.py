from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.knowledge import (
    CurriculumNode,
    ExerciseGenerationRun,
    ExerciseQuestion,
    KnowledgePoint,
)
from src.providers.router import ModelRouter
from src.runtime.hashing import stable_json_hash
from src.knowledge.unit_exercise_generation import (
    UNIT_GENERATOR_VERSION,
    generate_reviewed_unit_pool,
    select_generation_points,
)

PoolStatus = Literal["ready", "refreshing", "degraded", "generating"]


@dataclass(frozen=True)
class ExercisePoolSnapshot:
    questions: list[ExerciseQuestion]
    status: PoolStatus
    available_count: int
    target_count: int
    generation_run: ExerciseGenerationRun | None


async def get_exercise_pool(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    learner_id: uuid.UUID,
    schedule_refill: bool = True,
) -> ExercisePoolSnapshot:
    questions = await load_pool_questions(db, curriculum_node_id=curriculum_node_id)
    active_run = await _active_run(db, curriculum_node_id=curriculum_node_id)
    if schedule_refill and _needs_refill(questions) and active_run is None:
        active_run = await enqueue_exercise_refill(
            db,
            source_id=source_id,
            curriculum_node_id=curriculum_node_id,
            learner_id=learner_id,
            available_count=len(questions),
        )
    return ExercisePoolSnapshot(
        questions=questions,
        status=_pool_status(len(questions), active_run),
        available_count=len(questions),
        target_count=settings.exercise_pool_target_size,
        generation_run=active_run,
    )


async def load_pool_questions(
    db: AsyncSession,
    *,
    curriculum_node_id: uuid.UUID,
) -> list[ExerciseQuestion]:
    questions = await _load_published_questions(db, curriculum_node_id=curriculum_node_id)
    questions = [question for question in questions if _is_pool_eligible(question)]
    return sorted(questions, key=lambda item: (-_quality_score(item), str(item.id)))


async def _load_published_questions(
    db: AsyncSession,
    *,
    curriculum_node_id: uuid.UUID,
) -> list[ExerciseQuestion]:
    result = await db.execute(
        select(ExerciseQuestion)
        .where(
            ExerciseQuestion.curriculum_node_id == curriculum_node_id,
            ExerciseQuestion.status == "published",
            ExerciseQuestion.quality_status == "accepted",
        )
        .order_by(ExerciseQuestion.quality_score.desc(), ExerciseQuestion.created_at)
    )
    return list(result.scalars().all())


async def enqueue_exercise_refill(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    learner_id: uuid.UUID | None,
    available_count: int,
    priority: int = 100,
) -> ExerciseGenerationRun | None:
    points = await _load_generation_points(db, curriculum_node_id=curriculum_node_id)
    if not points:
        return None
    input_hash = _point_input_hash(points)
    dedupe_key = stable_json_hash(
        {
            "curriculum_node_id": str(curriculum_node_id),
            "input_hash": input_hash,
            "generator_version": UNIT_GENERATOR_VERSION,
        }
    )
    active_result = await db.execute(
        select(ExerciseGenerationRun).where(
            ExerciseGenerationRun.dedupe_key == dedupe_key,
            ExerciseGenerationRun.status.in_(("queued", "running")),
        )
    )
    active = active_result.scalar_one_or_none()
    if active is not None:
        return active

    requested_count = 16 if available_count < settings.exercise_pool_refill_threshold else 8
    run = ExerciseGenerationRun(
        source_id=source_id,
        curriculum_node_id=curriculum_node_id,
        requested_by_learner_id=learner_id,
        dedupe_key=dedupe_key,
        input_hash=input_hash,
        generator_version=UNIT_GENERATOR_VERSION,
        status="queued",
        priority=priority,
        requested_count=requested_count,
        metrics={"available_count_at_enqueue": available_count},
    )
    db.add(run)
    await db.flush()
    return run


async def claim_next_exercise_run(db: AsyncSession) -> ExerciseGenerationRun | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ExerciseGenerationRun)
        .where(
            or_(
                ExerciseGenerationRun.status == "queued",
                and_(
                    ExerciseGenerationRun.status == "running",
                    ExerciseGenerationRun.lease_expires_at < now,
                ),
            )
        )
        .order_by(ExerciseGenerationRun.priority.desc(), ExerciseGenerationRun.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None
    run.status = "running"
    run.attempt_count = (run.attempt_count or 0) + 1
    run.started_at = run.started_at or now
    run.lease_expires_at = now + timedelta(seconds=settings.exercise_worker_lease_seconds)
    run.error_message = None
    await db.flush()
    return run


async def process_exercise_generation_run(
    db: AsyncSession,
    *,
    run: ExerciseGenerationRun,
    model_router: ModelRouter,
) -> list[ExerciseQuestion]:
    node_result = await db.execute(
        select(CurriculumNode).where(CurriculumNode.id == run.curriculum_node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise ValueError("Curriculum node not found for exercise generation run")
    points = await _load_generation_points(db, curriculum_node_id=run.curriculum_node_id)
    all_existing = await _load_published_questions(db, curriculum_node_id=run.curriculum_node_id)
    existing = [question for question in all_existing if _is_pool_eligible(question)]
    questions = await generate_reviewed_unit_pool(
        db=db,
        model_router=model_router,
        learner_id=run.requested_by_learner_id,
        source_id=run.source_id,
        curriculum_node_id=run.curriculum_node_id,
        unit_title=node.title,
        points=points,
        existing_stems=[question.stem for question in all_existing],
        candidate_count=run.requested_count,
    )
    for question in questions:
        db.add(question)
    await db.flush()
    _archive_unreviewed_legacy_questions(all_existing, replacement_count=len(questions))

    run.status = "completed"
    run.generated_count = run.requested_count
    run.accepted_count = len(questions)
    run.rejected_count = max(0, run.generated_count - run.accepted_count)
    run.completed_at = datetime.now(timezone.utc)
    run.lease_expires_at = None
    run.metrics = {
        **(run.metrics or {}),
        "average_quality_score": round(
            sum(_quality_score(question) for question in questions) / len(questions), 4
        ),
        "pool_count_after_run": len(existing) + len(questions),
    }
    await db.flush()
    return questions


async def mark_exercise_run_failed(
    db: AsyncSession,
    *,
    run: ExerciseGenerationRun,
    error: Exception,
) -> None:
    run.error_message = str(error)[:500]
    run.lease_expires_at = None
    if run.attempt_count < settings.exercise_worker_max_attempts:
        run.status = "queued"
    else:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
    await db.flush()


async def maybe_enqueue_followup_refill(
    db: AsyncSession,
    *,
    run: ExerciseGenerationRun,
) -> ExerciseGenerationRun | None:
    questions = await load_pool_questions(db, curriculum_node_id=run.curriculum_node_id)
    if len(questions) >= settings.exercise_pool_target_size:
        return None
    return await enqueue_exercise_refill(
        db,
        source_id=run.source_id,
        curriculum_node_id=run.curriculum_node_id,
        learner_id=run.requested_by_learner_id,
        available_count=len(questions),
        priority=max(1, run.priority - 10),
    )


async def _load_generation_points(
    db: AsyncSession,
    *,
    curriculum_node_id: uuid.UUID,
) -> list[KnowledgePoint]:
    result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == curriculum_node_id,
            KnowledgePoint.status.in_(("published", "draft")),
        )
        .order_by(KnowledgePoint.created_at)
        .limit(80)
    )
    return select_generation_points(list(result.scalars().all()))


async def _active_run(
    db: AsyncSession,
    *,
    curriculum_node_id: uuid.UUID,
) -> ExerciseGenerationRun | None:
    result = await db.execute(
        select(ExerciseGenerationRun)
        .where(
            ExerciseGenerationRun.curriculum_node_id == curriculum_node_id,
            ExerciseGenerationRun.status.in_(("queued", "running")),
        )
        .order_by(ExerciseGenerationRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _point_input_hash(points: list[KnowledgePoint]) -> str:
    return stable_json_hash(
        [
            {
                "id": str(point.id),
                "canonical_key": point.canonical_key,
                "type": point.type,
                "title": point.title,
                "summary": point.summary,
                "content": point.content or {},
            }
            for point in points
        ]
    )


def _needs_refill(questions: list[ExerciseQuestion]) -> bool:
    current_generated = sum(
        question.generator_version == UNIT_GENERATOR_VERSION for question in questions
    )
    return (
        len(questions) < settings.exercise_pool_refill_threshold
        or current_generated < settings.exercise_pool_min_generated
    )


def _pool_status(count: int, active_run: ExerciseGenerationRun | None) -> PoolStatus:
    if count == 0:
        return "generating" if active_run is not None else "degraded"
    if count < settings.exercise_pool_ready_size:
        return "degraded" if active_run is None else "refreshing"
    return "refreshing" if active_run is not None else "ready"


def _is_pool_eligible(question: ExerciseQuestion) -> bool:
    metadata = question.metadata_ or {}
    generated = metadata.get("source_type") == "generated" or bool(metadata.get("generator"))
    if not generated:
        return True
    quality_gate = metadata.get("quality_gate") if isinstance(metadata.get("quality_gate"), dict) else {}
    return (
        question.generator_version == UNIT_GENERATOR_VERSION
        or quality_gate.get("status") == "accepted"
    )


def _archive_unreviewed_legacy_questions(
    questions: list[ExerciseQuestion],
    *,
    replacement_count: int,
) -> None:
    if replacement_count < settings.exercise_pool_ready_size:
        return
    for question in questions:
        metadata = question.metadata_ or {}
        generated = metadata.get("source_type") == "generated" or bool(metadata.get("generator"))
        quality_gate = metadata.get("quality_gate") if isinstance(metadata.get("quality_gate"), dict) else {}
        if generated and quality_gate.get("status") != "accepted":
            question.status = "archived"
            question.quality_status = "retired"


def _quality_score(question: ExerciseQuestion) -> float:
    value = question.quality_score
    return float(value) if isinstance(value, int | float) else 0.72
