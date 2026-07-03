import uuid
from dataclasses import dataclass
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.graph_checkpoint import LearningGraphCheckpoint
from src.models.knowledge import ExerciseAttempt
from src.models.learner import Learner
from src.models.memory import LearningMemoryEvent
from src.models.runtime import AgentEpisode


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    source: str
    allow_unclaimed_learners: bool = False


T = TypeVar("T")


async def get_learner_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    learner_id: uuid.UUID | str,
    *,
    allow_unclaimed_learners: bool = False,
) -> Learner:
    result = await db.execute(select(Learner).where(Learner.id == _as_uuid(learner_id)))
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    if not learner_belongs_to_user(
        learner,
        user_id,
        allow_unclaimed_learners=allow_unclaimed_learners,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Learner access denied")
    return learner


async def get_episode_for_learner(
    db: AsyncSession,
    learner_id: uuid.UUID | str,
    episode_id: uuid.UUID | str,
) -> AgentEpisode:
    return await _get_scoped_resource(
        db,
        AgentEpisode,
        learner_id=learner_id,
        resource_id=episode_id,
        detail="AgentEpisode not found",
    )


async def get_checkpoint_for_learner(
    db: AsyncSession,
    learner_id: uuid.UUID | str,
    checkpoint_id: uuid.UUID | str,
) -> LearningGraphCheckpoint:
    return await _get_scoped_resource(
        db,
        LearningGraphCheckpoint,
        learner_id=learner_id,
        resource_id=checkpoint_id,
        detail="LearningGraphCheckpoint not found",
    )


async def get_attempt_for_learner(
    db: AsyncSession,
    learner_id: uuid.UUID | str,
    attempt_id: uuid.UUID | str,
) -> ExerciseAttempt:
    return await _get_scoped_resource(
        db,
        ExerciseAttempt,
        learner_id=learner_id,
        resource_id=attempt_id,
        detail="ExerciseAttempt not found",
    )


async def get_memory_item_for_learner(
    db: AsyncSession,
    learner_id: uuid.UUID | str,
    memory_id: uuid.UUID | str,
) -> LearningMemoryEvent:
    return await _get_scoped_resource(
        db,
        LearningMemoryEvent,
        learner_id=learner_id,
        resource_id=memory_id,
        detail="Memory item not found",
    )


async def get_episode_for_user(
    db: AsyncSession,
    user: CurrentUser,
    episode_id: uuid.UUID | str,
) -> AgentEpisode:
    result = await db.execute(select(AgentEpisode).where(AgentEpisode.id == _as_uuid(episode_id)))
    episode = result.scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AgentEpisode not found")
    await get_learner_for_user(
        db,
        user.user_id,
        episode.learner_id,
        allow_unclaimed_learners=user.allow_unclaimed_learners,
    )
    return episode


def learner_belongs_to_user(
    learner: Learner | uuid.UUID,
    user_id: uuid.UUID,
    *,
    allow_unclaimed_learners: bool = False,
) -> bool:
    learner_id = learner if isinstance(learner, uuid.UUID) else getattr(learner, "id", None)
    owner_user_id = None if isinstance(learner, uuid.UUID) else getattr(learner, "tenant_id", None)

    if owner_user_id is None:
        return allow_unclaimed_learners or learner_id == user_id
    return owner_user_id == user_id


async def _get_scoped_resource(
    db: AsyncSession,
    model: type[T],
    *,
    learner_id: uuid.UUID | str,
    resource_id: uuid.UUID | str,
    detail: str,
) -> T:
    scoped_learner_id = _as_uuid(learner_id)
    result = await db.execute(
        select(model).where(
            model.id == _as_uuid(resource_id),
            model.learner_id == scoped_learner_id,
        )
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    if getattr(resource, "learner_id", scoped_learner_id) != scoped_learner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return resource


def _as_uuid(value: uuid.UUID | str | Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found") from exc
