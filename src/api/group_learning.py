import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, require_learner_access
from src.group_learning import (
    GroupLearningImportMessage,
    accept_signal,
    cleanup_expired_messages,
    delete_all_raw_messages,
    import_group_messages,
)
from src.models.group_learning import (
    GroupLearningMessage,
    GroupLearningParticipant,
    GroupLearningSignal,
    GroupLearningSource,
)
from src.models.learner import Learner

router = APIRouter(
    prefix="/api/learners/{learner_id}/group-learning",
    tags=["group-learning"],
)
import_router = APIRouter(prefix="/api/group-learning", tags=["group-learning"])

SourceStatus = Literal["active", "paused", "revoked"]
ParticipantRole = Literal["learner", "partner", "unknown"]
SignalStatus = Literal["candidate", "accepted", "dismissed"]
SignalAction = Literal[
    "accept",
    "dismiss",
    "restore",
    "delete",
    "apply_to_vocabulary",
    "apply_to_phrasebook",
    "apply_to_grammar",
]

RETENTION_OPTIONS = {1, 3, 7, 14, 30}
CONFIDENCE_OPTIONS = {0.7, 0.8, 0.9}


class SourceBaseRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    external_group_key: str = Field(min_length=1, max_length=255)
    status: SourceStatus = "active"
    raw_retention_days: int = Field(default=7, ge=1, le=30)
    auto_generate_recommendations: bool = True
    auto_write_candidates: bool = True
    auto_apply_high_confidence_tagged_signals: bool = False
    confidence_threshold: float = Field(default=0.8, ge=0, le=1)

    @field_validator("display_name", "external_group_key")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("raw_retention_days")
    @classmethod
    def retention_must_use_supported_option(cls, value: int) -> int:
        if value not in RETENTION_OPTIONS:
            raise ValueError("raw_retention_days must be one of 1, 3, 7, 14, 30")
        return value

    @field_validator("confidence_threshold")
    @classmethod
    def confidence_must_use_supported_option(cls, value: float) -> float:
        rounded = round(value, 2)
        if rounded not in CONFIDENCE_OPTIONS:
            raise ValueError("confidence_threshold must be one of 0.7, 0.8, 0.9")
        return rounded


class CreateSourceRequest(SourceBaseRequest):
    pass


class UpdateSourceRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    external_group_key: str | None = Field(default=None, min_length=1, max_length=255)
    status: SourceStatus | None = None
    raw_retention_days: int | None = Field(default=None, ge=1, le=30)
    auto_generate_recommendations: bool | None = None
    auto_write_candidates: bool | None = None
    auto_apply_high_confidence_tagged_signals: bool | None = None
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("display_name", "external_group_key")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("raw_retention_days")
    @classmethod
    def optional_retention_must_use_supported_option(cls, value: int | None) -> int | None:
        if value is not None and value not in RETENTION_OPTIONS:
            raise ValueError("raw_retention_days must be one of 1, 3, 7, 14, 30")
        return value

    @field_validator("confidence_threshold")
    @classmethod
    def optional_confidence_must_use_supported_option(cls, value: float | None) -> float | None:
        if value is None:
            return None
        rounded = round(value, 2)
        if rounded not in CONFIDENCE_OPTIONS:
            raise ValueError("confidence_threshold must be one of 0.7, 0.8, 0.9")
        return rounded


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    learner_id: uuid.UUID
    platform: str
    source_type: str
    display_name: str
    external_group_key: str
    status: str
    last_cursor: str | None = None
    last_seen_at: datetime | None = None
    last_import_summary: dict
    raw_retention_days: int
    auto_generate_recommendations: bool
    auto_write_candidates: bool
    auto_apply_high_confidence_tagged_signals: bool
    confidence_threshold: float
    pending_signal_count: int = 0
    participant_count: int = 0
    created_at: datetime
    updated_at: datetime


class ParticipantRequest(BaseModel):
    external_member_key: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    learner_id: uuid.UUID | None = None
    role: ParticipantRole = "unknown"
    analysis_enabled: bool = False

    @field_validator("external_member_key", "display_name")
    @classmethod
    def participant_text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class UpdateParticipantRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    learner_id: uuid.UUID | None = None
    role: ParticipantRole | None = None
    analysis_enabled: bool | None = None


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    external_member_key: str
    display_name: str
    learner_id: uuid.UUID | None = None
    role: str
    analysis_enabled: bool
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CleanupRequest(BaseModel):
    mode: Literal["expired", "all_raw_messages"] = "expired"
    keep_signal_evidence: bool = True


class CleanupResponse(BaseModel):
    deleted_raw_message_count: int


class ImportWechatMessageRequest(BaseModel):
    external_message_id: str = Field(min_length=1, max_length=255)
    external_member_key: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=120)
    content_text: str = Field(min_length=1)
    occurred_at: datetime
    message_type: str = "text"


class ImportWechatMessagesRequest(BaseModel):
    source_id: uuid.UUID
    messages: list[ImportWechatMessageRequest] = Field(min_length=1)


class ImportWechatMessagesResponse(BaseModel):
    source_id: uuid.UUID
    learner_id: uuid.UUID
    imported_count: int
    duplicate_count: int
    generated_signal_count: int
    ignored_count: int
    participant_count: int


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    learner_id: uuid.UUID
    signal_type: str
    category: str
    target_type: str
    target_label: str
    confidence: float
    evidence_text: str
    normalized_note: str | None = None
    recommendation_reason: str
    status: str
    applied_target_type: str | None = None
    applied_target_id: uuid.UUID | None = None
    metadata: dict
    source_display_name: str | None = None
    source_time: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UpdateSignalRequest(BaseModel):
    action: SignalAction


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[SourceResponse]:
    result = await db.execute(
        select(GroupLearningSource)
        .where(GroupLearningSource.learner_id == learner.id)
        .order_by(GroupLearningSource.created_at.asc())
    )
    sources = result.scalars().all()
    return [await _source_response(db, source) for source in sources]


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: CreateSourceRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> SourceResponse:
    await _ensure_unique_source_key(db, learner.id, body.external_group_key)
    source = GroupLearningSource(learner_id=learner.id, **body.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return await _source_response(db, source)


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    body: UpdateSourceRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> SourceResponse:
    source = await _get_owned_source(db, learner.id, source_id)
    updates = body.model_dump(exclude_unset=True)
    if "external_group_key" in updates:
        await _ensure_unique_source_key(db, learner.id, updates["external_group_key"], source_id)
    for key, value in updates.items():
        setattr(source, key, value)
    await db.flush()
    await db.refresh(source)
    return await _source_response(db, source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    delete_raw_messages: bool = Query(default=True),
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    source = await _get_owned_source(db, learner.id, source_id)
    if delete_raw_messages:
        await delete_all_raw_messages(db, source)
    await db.delete(source)
    await db.flush()


@router.get("/sources/{source_id}/participants", response_model=list[ParticipantResponse])
async def list_participants(
    source_id: uuid.UUID,
    q: str | None = Query(default=None),
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[GroupLearningParticipant]:
    await _get_owned_source(db, learner.id, source_id)
    query = select(GroupLearningParticipant).where(GroupLearningParticipant.source_id == source_id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            (GroupLearningParticipant.display_name.ilike(pattern))
            | (GroupLearningParticipant.external_member_key.ilike(pattern))
        )
    query = query.order_by(
        GroupLearningParticipant.last_message_at.desc().nullslast(),
        GroupLearningParticipant.display_name.asc(),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/sources/{source_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_participant(
    source_id: uuid.UUID,
    body: ParticipantRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> GroupLearningParticipant:
    await _get_owned_source(db, learner.id, source_id)
    _validate_participant_mapping(body.learner_id, body.role, body.analysis_enabled, learner.id)
    result = await db.execute(
        select(GroupLearningParticipant).where(
            GroupLearningParticipant.source_id == source_id,
            GroupLearningParticipant.external_member_key == body.external_member_key,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        participant = GroupLearningParticipant(source_id=source_id, **body.model_dump())
        db.add(participant)
    else:
        participant.display_name = body.display_name
        participant.learner_id = body.learner_id
        participant.role = body.role
        participant.analysis_enabled = body.analysis_enabled
    await db.flush()
    await db.refresh(participant)
    return participant


@router.patch("/participants/{participant_id}", response_model=ParticipantResponse)
async def update_participant(
    participant_id: uuid.UUID,
    body: UpdateParticipantRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> GroupLearningParticipant:
    participant = await _get_owned_participant(db, learner.id, participant_id)
    updates = body.model_dump(exclude_unset=True)
    next_learner_id = updates.get("learner_id", participant.learner_id)
    next_role = updates.get("role", participant.role)
    next_analysis_enabled = updates.get("analysis_enabled", participant.analysis_enabled)
    _validate_participant_mapping(next_learner_id, next_role, next_analysis_enabled, learner.id)
    for key, value in updates.items():
        setattr(participant, key, value)
    if participant.role != "learner":
        participant.analysis_enabled = False
        participant.learner_id = None
    await db.flush()
    await db.refresh(participant)
    return participant


@router.delete("/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_participant(
    participant_id: uuid.UUID,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    participant = await _get_owned_participant(db, learner.id, participant_id)
    await db.delete(participant)
    await db.flush()


@router.post("/sources/{source_id}/cleanup", response_model=CleanupResponse)
async def cleanup_source_messages(
    source_id: uuid.UUID,
    body: CleanupRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> CleanupResponse:
    source = await _get_owned_source(db, learner.id, source_id)
    if body.mode == "all_raw_messages":
        count = await delete_all_raw_messages(db, source)
    else:
        count = await cleanup_expired_messages(db, source)
    return CleanupResponse(deleted_raw_message_count=count)


@router.delete("/sources/{source_id}/messages", response_model=CleanupResponse)
async def delete_source_raw_messages(
    source_id: uuid.UUID,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> CleanupResponse:
    source = await _get_owned_source(db, learner.id, source_id)
    count = await delete_all_raw_messages(db, source)
    return CleanupResponse(deleted_raw_message_count=count)


@router.get("/signals", response_model=list[SignalResponse])
async def list_signals(
    status_filter: SignalStatus | Literal["all"] = Query(default="candidate", alias="status"),
    q: str | None = Query(default=None),
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[SignalResponse]:
    query = (
        select(GroupLearningSignal, GroupLearningMessage, GroupLearningSource)
        .join(GroupLearningMessage, GroupLearningMessage.id == GroupLearningSignal.message_id)
        .join(GroupLearningSource, GroupLearningSource.id == GroupLearningMessage.source_id)
        .where(GroupLearningSignal.learner_id == learner.id)
    )
    if status_filter != "all":
        query = query.where(GroupLearningSignal.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            (GroupLearningSignal.target_label.ilike(pattern))
            | (GroupLearningSignal.evidence_text.ilike(pattern))
            | (GroupLearningSignal.recommendation_reason.ilike(pattern))
        )
    query = query.order_by(GroupLearningSignal.created_at.desc())
    result = await db.execute(query)
    return [
        _signal_response(signal, message, source)
        for signal, message, source in result.all()
    ]


@router.patch("/signals/{signal_id}", response_model=SignalResponse)
async def update_signal(
    signal_id: uuid.UUID,
    body: UpdateSignalRequest,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> SignalResponse:
    signal, message, source = await _get_signal_context(db, learner.id, signal_id)
    if body.action in {"accept", "apply_to_vocabulary", "apply_to_phrasebook", "apply_to_grammar"}:
        signal = await accept_signal(db, signal)
    elif body.action == "dismiss":
        signal.status = "dismissed"
    elif body.action == "restore":
        signal.status = "candidate"
    elif body.action == "delete":
        signal.status = "deleted"
    await db.flush()
    await db.refresh(signal)
    return _signal_response(signal, message, source)


@router.delete("/signals/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal(
    signal_id: uuid.UUID,
    learner: Learner = Depends(require_learner_access),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    signal, _, _ = await _get_signal_context(db, learner.id, signal_id)
    await db.delete(signal)
    await db.flush()


@import_router.post("/wechat/messages/import", response_model=ImportWechatMessagesResponse)
async def import_wechat_messages(
    body: ImportWechatMessagesRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ImportWechatMessagesResponse:
    result = await db.execute(
        select(GroupLearningSource).where(GroupLearningSource.id == body.source_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Group learning source not found")
    try:
        summary = await import_group_messages(
            db,
            source_id=source.id,
            messages=[
                GroupLearningImportMessage(
                    external_message_id=message.external_message_id,
                    external_member_key=message.external_member_key,
                    content_text=message.content_text,
                    occurred_at=message.occurred_at,
                    display_name=message.display_name,
                    message_type=message.message_type,
                )
                for message in body.messages
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ImportWechatMessagesResponse(
        source_id=source.id,
        learner_id=source.learner_id,
        imported_count=summary.imported_count,
        duplicate_count=summary.duplicate_count,
        generated_signal_count=summary.generated_signal_count,
        ignored_count=summary.ignored_count,
        participant_count=summary.participant_count,
    )


async def _source_response(db: AsyncSession, source: GroupLearningSource) -> SourceResponse:
    pending_result = await db.execute(
        select(func.count())
        .select_from(GroupLearningSignal)
        .where(
            GroupLearningSignal.learner_id == source.learner_id,
            GroupLearningSignal.status == "candidate",
            GroupLearningSignal.message_id.in_(
                select(GroupLearningMessage.id).where(GroupLearningMessage.source_id == source.id)
            ),
        )
    )
    participant_result = await db.execute(
        select(func.count())
        .select_from(GroupLearningParticipant)
        .where(GroupLearningParticipant.source_id == source.id)
    )
    return SourceResponse(
        id=source.id,
        learner_id=source.learner_id,
        platform=source.platform,
        source_type=source.source_type,
        display_name=source.display_name,
        external_group_key=source.external_group_key,
        status=source.status,
        last_cursor=source.last_cursor,
        last_seen_at=source.last_seen_at,
        last_import_summary=source.last_import_summary or {},
        raw_retention_days=source.raw_retention_days,
        auto_generate_recommendations=source.auto_generate_recommendations,
        auto_write_candidates=source.auto_write_candidates,
        auto_apply_high_confidence_tagged_signals=(
            source.auto_apply_high_confidence_tagged_signals
        ),
        confidence_threshold=source.confidence_threshold,
        pending_signal_count=pending_result.scalar_one(),
        participant_count=participant_result.scalar_one(),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


async def _get_owned_source(
    db: AsyncSession,
    learner_id: uuid.UUID,
    source_id: uuid.UUID,
) -> GroupLearningSource:
    result = await db.execute(
        select(GroupLearningSource).where(
            GroupLearningSource.id == source_id,
            GroupLearningSource.learner_id == learner_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Group learning source not found")
    return source


async def _get_owned_participant(
    db: AsyncSession,
    learner_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> GroupLearningParticipant:
    result = await db.execute(
        select(GroupLearningParticipant, GroupLearningSource)
        .join(GroupLearningSource, GroupLearningSource.id == GroupLearningParticipant.source_id)
        .where(
            GroupLearningParticipant.id == participant_id,
            GroupLearningSource.learner_id == learner_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Group learning participant not found")
    return row[0]


async def _ensure_unique_source_key(
    db: AsyncSession,
    learner_id: uuid.UUID,
    external_group_key: str,
    exclude_source_id: uuid.UUID | None = None,
) -> None:
    query = select(GroupLearningSource.id).where(
        GroupLearningSource.learner_id == learner_id,
        GroupLearningSource.platform == "wechat",
        GroupLearningSource.external_group_key == external_group_key,
    )
    if exclude_source_id is not None:
        query = query.where(GroupLearningSource.id != exclude_source_id)
    result = await db.execute(query)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Group learning source already exists")


def _validate_participant_mapping(
    participant_learner_id: uuid.UUID | None,
    role: str,
    analysis_enabled: bool,
    current_learner_id: uuid.UUID,
) -> None:
    if role == "learner" and participant_learner_id != current_learner_id:
        raise HTTPException(status_code=422, detail="learner role must map to current learner")
    if analysis_enabled and role != "learner":
        raise HTTPException(status_code=422, detail="only learner role can enable analysis")


async def _get_signal_context(
    db: AsyncSession,
    learner_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> tuple[GroupLearningSignal, GroupLearningMessage, GroupLearningSource]:
    result = await db.execute(
        select(GroupLearningSignal, GroupLearningMessage, GroupLearningSource)
        .join(GroupLearningMessage, GroupLearningMessage.id == GroupLearningSignal.message_id)
        .join(GroupLearningSource, GroupLearningSource.id == GroupLearningMessage.source_id)
        .where(GroupLearningSignal.id == signal_id, GroupLearningSignal.learner_id == learner_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Group learning signal not found")
    return row[0], row[1], row[2]


def _signal_response(
    signal: GroupLearningSignal,
    message: GroupLearningMessage,
    source: GroupLearningSource,
) -> SignalResponse:
    return SignalResponse(
        id=signal.id,
        message_id=signal.message_id,
        learner_id=signal.learner_id,
        signal_type=signal.signal_type,
        category=_signal_category(signal.signal_type),
        target_type=signal.target_type,
        target_label=signal.target_label,
        confidence=signal.confidence,
        evidence_text=signal.evidence_text,
        normalized_note=signal.normalized_note,
        recommendation_reason=signal.recommendation_reason,
        status=signal.status,
        applied_target_type=signal.applied_target_type,
        applied_target_id=signal.applied_target_id,
        metadata=signal.metadata_ or {},
        source_display_name=source.display_name,
        source_time=message.occurred_at,
        created_at=signal.created_at,
        updated_at=signal.updated_at,
    )


def _signal_category(signal_type: str) -> str:
    if signal_type == "expression_gap":
        return "expression_gap"
    if signal_type in {"grammar_error", "grammar_correct_usage", "desired_grammar"}:
        return "grammar"
    if signal_type in {"desired_vocabulary", "vocabulary_candidate"}:
        return "vocabulary"
    if signal_type in {"good_sentence", "phrase_candidate"}:
        return "sentence"
    if signal_type == "note_candidate":
        return "note"
    return "intent"
