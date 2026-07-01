import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.exercises import ExerciseAttemptCreate, ExerciseAttemptService, ExerciseTarget
from src.exercises.attempt_service import ExerciseTargetType
from src.models.knowledge import ExerciseAttempt
from src.models.learner import Learner

router = APIRouter(
    prefix="/api/learners/{learner_id}/exercise-attempts",
    tags=["exercise-attempts"],
)

ExerciseAttemptResult = Literal["correct", "incorrect"]
ExerciseLearningStatus = Literal["mastered", "needs_review", "unstable", "not_started"]


class ExerciseTargetPayload(BaseModel):
    type: ExerciseTargetType
    id: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)

    @field_validator("id", "label")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class ExerciseAttemptCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, max_length=255)
    exercise_id: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("exerciseId", "exercise_id"),
        serialization_alias="exerciseId",
    )
    target: ExerciseTargetPayload
    answer: str = Field(min_length=1)
    result: ExerciseAttemptResult
    created_at: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("createdAt", "created_at"),
        serialization_alias="createdAt",
    )
    should_update_mastery: bool = True
    should_create_error_pattern: bool = False
    should_create_memory_evidence: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
    source_context: dict[str, object] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("sourceContext", "source_context"),
    )

    @field_validator("id", "exercise_id", "answer")
    @classmethod
    def text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class ExerciseAttemptResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    exercise_id: str = Field(serialization_alias="exerciseId")
    target: ExerciseTargetPayload
    answer: str
    result: ExerciseAttemptResult
    created_at: datetime = Field(serialization_alias="createdAt")
    should_update_mastery: bool
    should_create_error_pattern: bool
    should_create_memory_evidence: bool
    metadata: dict[str, object] = Field(default_factory=dict)
    source_context: dict[str, object] = Field(default_factory=dict, serialization_alias="sourceContext")


class ExerciseAttemptSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int
    correct: int
    incorrect: int
    accuracy: int
    last_attempt_at: datetime | None = Field(default=None, serialization_alias="lastAttemptAt")
    last_result: ExerciseAttemptResult | None = Field(default=None, serialization_alias="lastResult")
    needs_review: bool = Field(serialization_alias="needsReview")
    learning_status: ExerciseLearningStatus = Field(serialization_alias="learningStatus")


@router.get("", response_model=list[ExerciseAttemptResponse])
async def list_exercise_attempts(
    learner_id: uuid.UUID,
    target_type: ExerciseTargetType | None = Query(default=None),
    target_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[ExerciseAttemptResponse]:
    await _ensure_learner_exists(db, learner_id)
    attempts = await ExerciseAttemptService(db).list_attempts(learner_id, target_type, target_id)
    return [_attempt_response(attempt) for attempt in attempts]


@router.post(
    "",
    response_model=ExerciseAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_exercise_attempt(
    learner_id: uuid.UUID,
    body: ExerciseAttemptCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExerciseAttemptResponse:
    await _ensure_learner_exists(db, learner_id)
    attempt_id = _parse_uuid(body.id)
    client_attempt_id = body.id if body.id and attempt_id is None else None
    attempt = await ExerciseAttemptService(db).save_attempt(
        learner_id,
        ExerciseAttemptCreate(
            attempt_id=attempt_id,
            client_attempt_id=client_attempt_id,
            exercise_id=body.exercise_id,
            target=ExerciseTarget(
                type=body.target.type,
                id=body.target.id,
                label=body.target.label,
            ),
            answer=body.answer,
            result=body.result,
            created_at=body.created_at,
            metadata=body.metadata,
            source_context=body.source_context,
            should_update_mastery=body.should_update_mastery,
            should_create_error_pattern=body.should_create_error_pattern,
            should_create_memory_evidence=body.should_create_memory_evidence,
        ),
    )
    return _attempt_response(attempt)


@router.get("/summary", response_model=ExerciseAttemptSummaryResponse)
async def get_exercise_attempt_summary(
    learner_id: uuid.UUID,
    target_type: ExerciseTargetType | None = Query(default=None),
    target_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> ExerciseAttemptSummaryResponse:
    await _ensure_learner_exists(db, learner_id)
    summary = await ExerciseAttemptService(db).get_summary(learner_id, target_type, target_id)
    return ExerciseAttemptSummaryResponse(
        total=summary.total,
        correct=summary.correct,
        incorrect=summary.incorrect,
        accuracy=summary.accuracy,
        last_attempt_at=summary.last_attempt_at,
        last_result=summary.last_result,
        needs_review=summary.needs_review,
        learning_status=summary.learning_status,
    )


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _attempt_response(attempt: ExerciseAttempt) -> ExerciseAttemptResponse:
    return ExerciseAttemptResponse(
        id=str(attempt.id),
        exercise_id=attempt.exercise_id,
        target=ExerciseTargetPayload(
            type=attempt.target_type,
            id=attempt.target_id,
            label=attempt.target_label,
        ),
        answer=attempt.answer,
        result=attempt.result,
        created_at=attempt.created_at,
        should_update_mastery=attempt.should_update_mastery,
        should_create_error_pattern=attempt.should_create_error_pattern,
        should_create_memory_evidence=attempt.should_create_memory_evidence,
        metadata=attempt.metadata_ or {},
        source_context=attempt.source_context or {},
    )


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
