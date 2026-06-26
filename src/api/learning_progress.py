import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.learner import Learner
from src.models.learning_progress import LearningProgressItem

router = APIRouter(
    prefix="/api/learners/{learner_id}/learning-progress",
    tags=["learning-progress"],
)

LearningSkill = Literal["grammar", "pronunciation", "writing_phrase"]
ProgressStatus = Literal["opened", "learned"]


class LearningProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    skill: str
    item_id: str
    title: str
    status: str
    is_favorite: bool
    opened_count: int
    last_opened_at: datetime | None = None
    learned_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UpdateLearningProgressRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: ProgressStatus | None = None
    is_favorite: bool | None = None
    mark_opened: bool = False
    mark_learned: bool = False
    metadata: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _response(item: LearningProgressItem) -> LearningProgressResponse:
    return LearningProgressResponse(
        id=item.id,
        learner_id=item.learner_id,
        skill=item.skill,
        item_id=item.item_id,
        title=item.title,
        status=item.status,
        is_favorite=bool(item.is_favorite),
        opened_count=item.opened_count or 0,
        last_opened_at=item.last_opened_at,
        learned_at=item.learned_at,
        metadata=item.metadata_ or {},
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=list[LearningProgressResponse])
async def list_learning_progress(
    learner_id: uuid.UUID,
    skill: LearningSkill | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[LearningProgressResponse]:
    await _ensure_learner_exists(db, learner_id)

    query = select(LearningProgressItem).where(LearningProgressItem.learner_id == learner_id)
    if skill is not None:
        query = query.where(LearningProgressItem.skill == skill)
    query = query.order_by(
        LearningProgressItem.is_favorite.desc(),
        LearningProgressItem.learned_at.desc().nullslast(),
        LearningProgressItem.last_opened_at.desc().nullslast(),
        LearningProgressItem.updated_at.desc(),
    )
    result = await db.execute(query)
    return [_response(item) for item in result.scalars().all()]


@router.put("/{skill}/{item_id}", response_model=LearningProgressResponse)
async def update_learning_progress(
    learner_id: uuid.UUID,
    skill: LearningSkill,
    item_id: str,
    body: UpdateLearningProgressRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LearningProgressResponse:
    await _ensure_learner_exists(db, learner_id)
    normalized_item_id = item_id.strip()
    if not normalized_item_id:
        raise HTTPException(status_code=422, detail="item_id must not be blank")

    result = await db.execute(
        select(LearningProgressItem).where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == skill,
            LearningProgressItem.item_id == normalized_item_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = LearningProgressItem(
            learner_id=learner_id,
            skill=skill,
            item_id=normalized_item_id,
            title=body.title or normalized_item_id,
            status="opened",
            is_favorite=False,
            opened_count=0,
            metadata_={},
        )
        db.add(item)

    now = datetime.now(timezone.utc)
    if body.title is not None:
        item.title = body.title
    if body.metadata is not None:
        item.metadata_ = body.metadata
    if body.is_favorite is not None:
        item.is_favorite = body.is_favorite
    if body.status is not None:
        item.status = body.status
        if body.status == "learned" and item.learned_at is None:
            item.learned_at = now
    if body.mark_opened:
        item.opened_count = (item.opened_count or 0) + 1
        item.last_opened_at = now
    if body.mark_learned:
        item.status = "learned"
        item.learned_at = now

    await db.flush()
    await db.refresh(item)
    return _response(item)
