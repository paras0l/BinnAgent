import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import ExerciseQuestion, KnowledgePoint
from src.knowledge.unit_exercise_generation import (
    MIN_PUBLISHABLE_QUESTIONS,
    UNIT_GENERATOR_VERSION,
    UnitExerciseGenerationUnavailableError,
    generate_reviewed_unit_pool,
    select_generation_points,
)
from src.providers.router import ModelRouter


async def ensure_unit_exercises(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    learner_id: uuid.UUID,
    unit_title: str,
    model_router: ModelRouter,
) -> list[ExerciseQuestion]:
    existing_result = await db.execute(
        select(ExerciseQuestion)
        .where(
            ExerciseQuestion.curriculum_node_id == curriculum_node_id,
            ExerciseQuestion.status == "published",
        )
        .order_by(ExerciseQuestion.created_at)
    )
    existing = list(existing_result.scalars().all())
    current = [question for question in existing if _is_current_generated_question(question)]
    curated = [question for question in existing if not _is_generated_question(question)]
    if len(current) + len(curated) >= MIN_PUBLISHABLE_QUESTIONS:
        return [*curated, *current]

    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == curriculum_node_id,
            KnowledgePoint.status.in_(("published", "draft")),
        )
        .order_by(KnowledgePoint.created_at)
        .limit(80)
    )
    points = select_generation_points(list(point_result.scalars().all()))
    generation_error: Exception | None = None
    questions: list[ExerciseQuestion] = []
    for _attempt in range(2):
        try:
            questions = await generate_reviewed_unit_pool(
                db=db,
                model_router=model_router,
                learner_id=learner_id,
                source_id=source_id,
                curriculum_node_id=curriculum_node_id,
                unit_title=unit_title,
                points=points,
                existing_stems=[question.stem for question in existing],
            )
            break
        except Exception as exc:
            generation_error = exc
    if not questions:
        if curated:
            return curated
        if isinstance(generation_error, UnitExerciseGenerationUnavailableError):
            raise generation_error
        raise UnitExerciseGenerationUnavailableError(
            "AI unit exercise generation failed"
        ) from generation_error

    for question in existing:
        if _is_generated_question(question):
            question.status = "archived"

    for question in questions:
        db.add(question)
    await db.flush()
    return [*curated, *questions]


def _is_generated_question(question: ExerciseQuestion) -> bool:
    metadata = question.metadata_ or {}
    return metadata.get("source_type") == "generated" or bool(metadata.get("generator"))


def _is_current_generated_question(question: ExerciseQuestion) -> bool:
    metadata = question.metadata_ or {}
    quality_gate = metadata.get("quality_gate") or {}
    return (
        metadata.get("generator_version") == UNIT_GENERATOR_VERSION
        and quality_gate.get("status") == "accepted"
    )
