import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.learner import Learner, LearnerProfile

router = APIRouter(prefix="/api/learners", tags=["learners"])


# --- Request schemas ---


class CreateLearnerRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("nickname")
    @classmethod
    def nickname_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Nickname must not be blank")
        return stripped


class CreateProfileRequest(BaseModel):
    target_exam: Optional[str] = Field(default=None, max_length=50)
    target_score: Optional[int] = Field(default=None, ge=0, le=710)
    exam_date: Optional[date] = None
    daily_time_budget_minutes: Optional[int] = Field(default=None, ge=1, le=600)


# --- Response schemas ---


class LearnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nickname: str
    email: Optional[str] = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    learner_id: uuid.UUID
    target_exam: Optional[str] = None
    target_score: Optional[int] = None
    exam_date: Optional[date] = None
    daily_time_budget_minutes: Optional[int] = None


# --- Endpoints ---


@router.post("", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
async def create_learner(
    body: CreateLearnerRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    learner = Learner(nickname=body.nickname, email=body.email)
    db.add(learner)
    await db.flush()
    await db.refresh(learner)
    return learner


@router.get("/{learner_id}", response_model=LearnerResponse)
async def get_learner(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return learner


@router.post(
    "/{learner_id}/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    learner_id: uuid.UUID,
    body: CreateProfileRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LearnerProfile:
    # Verify learner exists
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    # Check profile doesn't already exist
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Profile already exists")

    profile = LearnerProfile(
        learner_id=learner_id,
        target_exam=body.target_exam,
        target_score=body.target_score,
        exam_date=body.exam_date,
        daily_time_budget_minutes=body.daily_time_budget_minutes,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/{learner_id}/profile", response_model=ProfileResponse)
async def get_profile(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> LearnerProfile:
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
