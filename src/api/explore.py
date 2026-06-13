import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.explore import ExploreFeaturePreference
from src.models.learner import Learner

router = APIRouter(prefix="/api/learners/{learner_id}/explore", tags=["explore"])


class ExplorePreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    feature_id: str
    is_favorite: bool
    priority: int
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UpdateExplorePreferenceRequest(BaseModel):
    is_favorite: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    mark_used: bool = False


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


@router.get("/preferences", response_model=list[ExplorePreferenceResponse])
async def list_explore_preferences(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ExploreFeaturePreference]:
    await _ensure_learner_exists(db, learner_id)
    result = await db.execute(
        select(ExploreFeaturePreference)
        .where(ExploreFeaturePreference.learner_id == learner_id)
        .order_by(
            ExploreFeaturePreference.is_favorite.desc(),
            ExploreFeaturePreference.priority.desc(),
            ExploreFeaturePreference.updated_at.desc(),
        )
    )
    return list(result.scalars().all())


@router.put(
    "/preferences/{feature_id}",
    response_model=ExplorePreferenceResponse,
)
async def update_explore_preference(
    learner_id: uuid.UUID,
    feature_id: str,
    body: UpdateExplorePreferenceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExploreFeaturePreference:
    await _ensure_learner_exists(db, learner_id)
    normalized_feature_id = feature_id.strip()
    if not normalized_feature_id:
        raise HTTPException(status_code=422, detail="feature_id must not be blank")

    result = await db.execute(
        select(ExploreFeaturePreference).where(
            ExploreFeaturePreference.learner_id == learner_id,
            ExploreFeaturePreference.feature_id == normalized_feature_id,
        )
    )
    preference = result.scalar_one_or_none()
    if preference is None:
        preference = ExploreFeaturePreference(
            learner_id=learner_id,
            feature_id=normalized_feature_id,
            is_favorite=False,
            priority=0,
        )
        db.add(preference)

    if body.is_favorite is not None:
        preference.is_favorite = body.is_favorite
        if body.is_favorite and body.priority is None and preference.priority == 0:
            preference.priority = 100
    if body.priority is not None:
        preference.priority = body.priority
    if body.mark_used:
        preference.last_used_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(preference)
    return preference
