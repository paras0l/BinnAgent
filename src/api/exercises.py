import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.exercises.attempt_service import ExerciseTargetType
from src.exercises.item_mapper import exercise_question_to_item
from src.knowledge.exercises import ensure_unit_exercises
from src.models.knowledge import CurriculumNode
from src.models.learner import Learner

router = APIRouter(
    prefix="/api/learners/{learner_id}/exercises",
    tags=["exercises"],
)


@router.get("")
async def list_exercises_for_target(
    learner_id: uuid.UUID,
    target_type: ExerciseTargetType = Query(),
    target_id: str = Query(min_length=1),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    await _ensure_learner_exists(db, learner_id)
    if target_type != "curriculum_node":
        return []

    curriculum_node_id = _parse_uuid(target_id, "target_id must be a valid curriculum node id")
    result = await db.execute(select(CurriculumNode).where(CurriculumNode.id == curriculum_node_id))
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")

    questions = await ensure_unit_exercises(
        db,
        source_id=node.source_id,
        curriculum_node_id=node.id,
    )
    return [
        exercise_question_to_item(question, target_label=node.title)
        for question in questions[:limit]
    ]


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _parse_uuid(value: str, error: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=error) from exc
