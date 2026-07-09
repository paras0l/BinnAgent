import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
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

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip().lower()
        return stripped or None


class LoginLearnerRequest(CreateLearnerRequest):
    pass


class CreateProfileRequest(BaseModel):
    target_exam: Optional[str] = Field(default=None, max_length=50)
    target_score: Optional[int] = Field(default=None, ge=0, le=710)
    exam_date: Optional[date] = None
    current_level: Optional[str] = Field(default=None, max_length=20)
    daily_time_budget_minutes: Optional[int] = Field(default=None, ge=1, le=600)

    @field_validator("target_exam", "current_level")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


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
    current_level: Optional[str] = None
    daily_time_budget_minutes: Optional[int] = None


class ProfileReadinessResponse(BaseModel):
    learner_id: uuid.UUID
    target_exam: Optional[str] = None
    current_level: Optional[str] = None
    has_learning_goal: bool
    has_current_level: bool
    is_complete: bool


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


@router.post("/login", response_model=LearnerResponse)
async def login_learner(
    body: LoginLearnerRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    if body.email:
        result = await db.execute(select(Learner).where(Learner.email == body.email))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

    nickname_result = await db.execute(
        select(Learner)
        .where(func.lower(Learner.nickname) == body.nickname.lower())
        .order_by(Learner.created_at.asc())
    )
    existing_by_nickname = nickname_result.scalars().first()
    if existing_by_nickname is not None:
        if body.email and existing_by_nickname.email is None:
            existing_by_nickname.email = body.email
            await db.flush()
            await db.refresh(existing_by_nickname)
        return existing_by_nickname

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


@router.get("/{learner_id}/profile-readiness", response_model=ProfileReadinessResponse)
async def get_profile_readiness(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ProfileReadinessResponse:
    result = await db.execute(
        select(Learner.id, LearnerProfile.target_exam, LearnerProfile.current_level)
        .select_from(Learner)
        .outerjoin(LearnerProfile, LearnerProfile.learner_id == Learner.id)
        .where(Learner.id == learner_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    _, target_exam, current_level = row
    has_learning_goal = bool((target_exam or "").strip())
    has_current_level = bool((current_level or "").strip())
    return ProfileReadinessResponse(
        learner_id=learner_id,
        target_exam=target_exam,
        current_level=current_level,
        has_learning_goal=has_learning_goal,
        has_current_level=has_current_level,
        is_complete=has_learning_goal and has_current_level,
    )


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
        current_level=body.current_level,
        daily_time_budget_minutes=body.daily_time_budget_minutes,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.put("/{learner_id}/profile", response_model=ProfileResponse)
async def upsert_profile(
    learner_id: uuid.UUID,
    body: CreateProfileRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LearnerProfile:
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = LearnerProfile(learner_id=learner_id)
        db.add(profile)

    profile.target_exam = body.target_exam
    profile.target_score = body.target_score
    profile.exam_date = body.exam_date
    profile.current_level = body.current_level
    profile.daily_time_budget_minutes = body.daily_time_budget_minutes
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
