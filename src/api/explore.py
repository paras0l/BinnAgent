import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.explore.capabilities import explore_capability_registry
from src.explore.recommender import ExploreCapabilityRecommender
from src.explore.schemas import (
    ExploreCapabilityEventRequest,
    ExploreCapabilitySpec,
    ExploreCapabilityStartResponse,
    ExploreRecommendationsRequest,
    ExploreRecommendationsResponse,
    ExploreRecommendationContext,
    StartExploreCapabilityRequest,
)
from src.learning.orchestrator import LearningOrchestrator
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.explore import ExploreFeaturePreference
from src.models.learner import Learner
from src.runtime.episode import EpisodeRuntime
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy

router = APIRouter(prefix="/api/learners/{learner_id}/explore", tags=["explore"])
capabilities_router = APIRouter(prefix="/api/explore", tags=["explore"])


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


@capabilities_router.get("/capabilities", response_model=list[ExploreCapabilitySpec])
async def list_explore_capabilities(
    status: str | None = Query(default=None, max_length=30),
    category: str | None = Query(default=None, max_length=40),
    ready_only: bool = False,
) -> list[ExploreCapabilitySpec]:
    return explore_capability_registry.list(
        status=status,
        category=category,
        ready_only=ready_only,
    )


@capabilities_router.post(
    "/capabilities/{capability_id}/start",
    response_model=ExploreCapabilityStartResponse,
)
async def start_explore_capability(
    capability_id: str,
    body: StartExploreCapabilityRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExploreCapabilityStartResponse:
    await _ensure_learner_exists(db, body.learner_id)
    spec = explore_capability_registry.get(capability_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Explore capability not found")
    if spec.status == "todo":
        raise HTTPException(status_code=409, detail="Explore capability is not ready")

    target_id = body.target_id or f"explore:{capability_id}"
    task_spec = TaskSpec(
        task_id=f"explore:{capability_id}:{uuid.uuid4().hex[:12]}",
        task_type=spec.task_type or "explore_capability",
        source="explore",
        objective=spec.title,
        target=TaskTarget(
            target_type=spec.target_type or "explore_capability",
            target_id=target_id,
            label=spec.title,
            metadata={
                "capability_id": capability_id,
                "feature_id": spec.feature_id,
                "category": spec.category,
                "learning_skill": spec.learning_skill,
                **body.metadata,
            },
        ),
        difficulty=body.difficulty or spec.default_difficulty,
        allowed_tools=spec.allowed_tools,
        success_criteria=SuccessCriteria(min_accuracy=0.8, requires_explanation=True),
        verification_policy=VerificationPolicy(
            required_checks=["episode_started"],
            require_evidence=False,
        ),
        metadata={
            "capability_id": capability_id,
            "feature_id": spec.feature_id,
            "category": spec.category,
            "learning_skill": spec.learning_skill,
            "produces": spec.produces,
            **body.metadata,
        },
    )
    started = await LearningOrchestrator(db).start_task(
        learner_id=body.learner_id,
        task_spec=task_spec,
        recommendation_reason=f"Explore capability: {spec.title}",
    )
    return ExploreCapabilityStartResponse(
        episode_id=started.episode_id,
        task_spec=started.task_spec.model_dump(mode="json") if started.task_spec else None,
        status=started.status,
        answer_required=started.answer_required,
        prompt=started.prompt,
        initial_payload=started.initial_payload,
    )


@router.post("/recommendations", response_model=ExploreRecommendationsResponse)
async def recommend_explore_capabilities(
    learner_id: uuid.UUID,
    body: ExploreRecommendationsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExploreRecommendationsResponse:
    await _ensure_learner_exists(db, learner_id)
    recommendations = await ExploreCapabilityRecommender(db).recommend(
        ExploreRecommendationContext(
            learner_id=learner_id,
            episode_id=body.episode_id,
            task_spec=body.task_spec,
            knowledge_point_id=body.knowledge_point_id,
            knowledge_point_title=body.knowledge_point_title,
            learning_skill=body.learning_skill,
            subskill=body.subskill,
            grading_result=body.grading_result,
            mastery_update=body.mastery_update,
            memory_context=body.memory_context,
            evidence_refs=body.evidence_refs,
            metadata=body.metadata,
        )
    )
    return ExploreRecommendationsResponse(recommendations=recommendations)


@router.post("/capabilities/{capability_id}/events")
async def record_explore_capability_event(
    learner_id: uuid.UUID,
    capability_id: str,
    body: ExploreCapabilityEventRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner_exists(db, learner_id)
    spec = explore_capability_registry.get(capability_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Explore capability not found")

    event_type = f"explore_capability_{body.event_type}"
    payload = {
        "recommendation_id": body.recommendation_id,
        "episode_id": str(body.episode_id) if body.episode_id else None,
        "capability_id": spec.capability_id,
        "feature_id": spec.feature_id,
        "title": spec.title,
        "category": spec.category,
        "reason": body.reason or body.metadata.get("reason"),
        "evidence_refs": body.evidence_refs,
        "metadata": body.metadata,
    }
    memory_event = await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type=event_type,
            skill=spec.learning_skill,
            source_type="explore_capability",
            source_id=spec.capability_id,
            payload=payload,
            confidence=1.0,
            created_by="user",
        )
    )
    if body.event_type == "clicked":
        await _upsert_capability_preference(db, learner_id, spec.feature_id, mark_used=True)
    if body.episode_id:
        await EpisodeRuntime(db).append_event(
            episode_id=body.episode_id,
            learner_id=learner_id,
            event_type=event_type,
            source_module="explore",
            target_type="explore_capability",
            target_id=spec.capability_id,
            payload=payload,
        )
    await db.flush()
    return {"memory_event_id": str(memory_event.id), "event_type": event_type}


async def _upsert_capability_preference(
    db: AsyncSession,
    learner_id: uuid.UUID,
    feature_id: str,
    *,
    mark_used: bool = False,
) -> ExploreFeaturePreference:
    result = await db.execute(
        select(ExploreFeaturePreference).where(
            ExploreFeaturePreference.learner_id == learner_id,
            ExploreFeaturePreference.feature_id == feature_id,
        )
    )
    preference = result.scalar_one_or_none()
    if preference is None:
        preference = ExploreFeaturePreference(
            learner_id=learner_id,
            feature_id=feature_id,
            is_favorite=False,
            priority=0,
        )
        db.add(preference)
    if mark_used:
        preference.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return preference
