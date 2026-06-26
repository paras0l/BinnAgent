import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.exercise_blueprints import build_exercise_blueprints
from src.knowledge.exercise_generator import build_question
from src.knowledge.exercise_linter import lint_exercise_set
from src.models.knowledge import ExerciseQuestion, KnowledgePoint


async def ensure_unit_exercises(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
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
    if existing:
        return existing

    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == curriculum_node_id,
            KnowledgePoint.status.in_(("published", "draft")),
        )
        .order_by(KnowledgePoint.created_at)
        .limit(12)
    )
    points = list(point_result.scalars().all())
    blueprints = build_exercise_blueprints(points, target_count=8)
    questions = [
        build_question(
            blueprint,
            source_id=source_id,
            curriculum_node_id=curriculum_node_id,
            peers=points,
        )
        for blueprint in blueprints
    ]
    lint_errors = lint_exercise_set(questions)
    if lint_errors:
        raise ValueError(f"Generated exercise set failed quality checks: {', '.join(lint_errors)}")

    for question in questions:
        db.add(question)
    await db.flush()
    return questions
