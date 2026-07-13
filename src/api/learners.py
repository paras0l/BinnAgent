import hmac
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.auth.email_verification import email_verification_token_is_valid, normalize_email
from src.config import settings
from src.models.learner import Learner, LearnerProfile, generate_invite_code

router = APIRouter(prefix="/api/learners", tags=["learners"])


# --- Request schemas ---


def _normalize_invite_code(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Invitation code must not be blank")
    return normalized


class CreateLearnerRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    invite_code: str = Field(min_length=1, max_length=32)
    verification_token: str = Field(min_length=20, max_length=2048)

    @field_validator("nickname")
    @classmethod
    def nickname_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Nickname must not be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("invite_code")
    @classmethod
    def normalize_invite_code(cls, value: str) -> str:
        return _normalize_invite_code(value)


class LookupLearnersRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    verification_token: str = Field(min_length=20, max_length=2048)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginLearnerRequest(LookupLearnersRequest):
    learner_id: uuid.UUID


class BindLearnerEmailRequest(LookupLearnersRequest):
    pass


class CreateProfileRequest(BaseModel):
    learning_track: Literal["school", "exam", "general", "reading"] = "school"
    target_exam: Optional[str] = Field(default=None, max_length=50)
    target_score: Optional[int] = Field(default=None, ge=0, le=710)
    exam_date: Optional[date] = None
    current_level: Optional[str] = Field(default=None, max_length=20)
    daily_time_budget_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    interest_topics: list[str] = Field(default_factory=list, max_length=20)

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
    invite_code: Optional[str] = None


class LearnerAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nickname: str


class LearnerLookupResponse(BaseModel):
    email: str
    accounts: list[LearnerAccountResponse]


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    learner_id: uuid.UUID
    learning_track: str = "school"
    target_exam: Optional[str] = None
    target_score: Optional[int] = None
    exam_date: Optional[date] = None
    current_level: Optional[str] = None
    daily_time_budget_minutes: Optional[int] = None
    interest_topics: list[str] = Field(default_factory=list)

    @field_validator("learning_track", mode="before")
    @classmethod
    def default_learning_track(cls, value: object) -> str:
        return value if isinstance(value, str) and value else "school"

    @field_validator("interest_topics", mode="before")
    @classmethod
    def default_interest_topics(cls, value: object) -> list[str]:
        return value if isinstance(value, list) else []


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
    _require_verified_email(body.email, body.verification_token)
    inviter_result = await db.execute(
        select(Learner).where(Learner.invite_code == body.invite_code)
    )
    inviter = inviter_result.scalar_one_or_none()

    if inviter is None:
        learner_count_result = await db.execute(select(func.count()).select_from(Learner))
        learner_count = learner_count_result.scalar_one()
        bootstrap_code = settings.bootstrap_invite_code
        is_bootstrap_registration = (
            learner_count == 0
            and bool(bootstrap_code and bootstrap_code.strip())
            and hmac.compare_digest(body.invite_code, _normalize_invite_code(bootstrap_code))
        )
        if not is_bootstrap_registration:
            raise HTTPException(status_code=400, detail="Invalid invitation code")

    learner = Learner(
        nickname=body.nickname,
        email=body.email,
        invite_code=generate_invite_code(),
        invited_by_learner_id=inviter.id if inviter is not None else None,
    )
    db.add(learner)
    await db.flush()
    await db.refresh(learner)
    return learner


@router.post("/lookup", response_model=LearnerLookupResponse)
async def lookup_learners(
    body: LookupLearnersRequest,
    db: AsyncSession = Depends(get_db_session),
) -> LearnerLookupResponse:
    _require_verified_email(body.email, body.verification_token)
    result = await db.execute(
        select(Learner)
        .where(Learner.email == body.email)
        .order_by(Learner.created_at.asc(), Learner.id.asc())
    )
    return LearnerLookupResponse(email=body.email, accounts=list(result.scalars().all()))


@router.post("/login", response_model=LearnerResponse)
async def login_learner(
    body: LoginLearnerRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    _require_verified_email(body.email, body.verification_token)
    result = await db.execute(
        select(Learner).where(
            Learner.id == body.learner_id,
            Learner.email == body.email,
        )
    )
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found for this email")
    return learner


@router.put("/{learner_id}/email", response_model=LearnerResponse)
async def bind_learner_email(
    learner_id: uuid.UUID,
    body: BindLearnerEmailRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Learner:
    _require_verified_email(body.email, body.verification_token)
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    if learner.email is not None and learner.email != body.email:
        raise HTTPException(status_code=409, detail="Learner email is already bound")

    learner.email = body.email
    await db.flush()
    await db.refresh(learner)
    return learner


def _require_verified_email(email: str, token: str) -> None:
    if not email_verification_token_is_valid(email=email, token=token):
        raise HTTPException(status_code=401, detail="Email verification required")


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
        learning_track=body.learning_track,
        target_exam=body.target_exam,
        target_score=body.target_score,
        exam_date=body.exam_date,
        current_level=body.current_level,
        daily_time_budget_minutes=body.daily_time_budget_minutes,
        interest_topics=body.interest_topics,
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
    profile.learning_track = body.learning_track
    profile.target_score = body.target_score
    profile.exam_date = body.exam_date
    profile.current_level = body.current_level
    profile.daily_time_budget_minutes = body.daily_time_budget_minutes
    profile.interest_topics = body.interest_topics
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/{learner_id}/profile", response_model=ProfileResponse)
async def get_profile(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> LearnerProfile | ProfileResponse:
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    learner_result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if learner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return ProfileResponse(learner_id=learner_id)
