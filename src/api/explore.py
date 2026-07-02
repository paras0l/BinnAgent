import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.learning.orchestrator import LearningOrchestrator
from src.models.explore import ExploreFeaturePreference
from src.models.learner import Learner
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy

router = APIRouter(prefix="/api/learners/{learner_id}/explore", tags=["explore"])
skills_router = APIRouter(prefix="/api/explore", tags=["explore"])


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


class ExploreSkillSpec(BaseModel):
    skill_id: str
    title: str
    description: str
    task_type: str
    target_type: str | None = None
    default_difficulty: str | None = None
    estimated_minutes: int | None = None
    required_tools: list[str]
    produces: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartExploreSkillRequest(BaseModel):
    learner_id: uuid.UUID
    target_id: str | None = None
    difficulty: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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


EXPLORE_SKILLS: dict[str, ExploreSkillSpec] = {
    "vocabulary_practice": ExploreSkillSpec(
        skill_id="vocabulary_practice",
        title="词汇专项练习",
        description="从探索入口创建词汇练习任务，并进入 AgentEpisode Runtime。",
        task_type="practice_vocabulary",
        target_type="vocabulary",
        default_difficulty="adaptive",
        estimated_minutes=8,
        required_tools=["memory.retrieve", "exercise.grade", "mastery.update", "review.schedule"],
        produces=["attempt", "memory_event", "mastery_update", "review_schedule"],
        metadata={"entrypoint": "explore"},
    ),
    "writing_phrase_practice": ExploreSkillSpec(
        skill_id="writing_phrase_practice",
        title="写作句式练习",
        description="创建写作句式练习 TaskSpec，后续接入句式题目 handler。",
        task_type="practice_writing_phrase",
        target_type="writing_phrase",
        default_difficulty="adaptive",
        estimated_minutes=10,
        required_tools=["exercise.grade", "mastery.update", "memory.write"],
        produces=["attempt", "memory_event", "mastery_update"],
        metadata={"entrypoint": "explore"},
    ),
    "grammar_micro_lesson": ExploreSkillSpec(
        skill_id="grammar_micro_lesson",
        title="语法微课",
        description="创建语法微知识点 TaskSpec，复用知识学习 runtime。",
        task_type="learn_knowledge_point",
        target_type="knowledge_point",
        default_difficulty="easy",
        estimated_minutes=6,
        required_tools=["rag.retrieve", "exercise.grade", "mastery.update", "verification.verify_episode"],
        produces=["attempt", "memory_event", "mastery_update", "review_schedule"],
        metadata={"entrypoint": "explore"},
    ),
    "knowledge_practice": ExploreSkillSpec(
        skill_id="knowledge_practice",
        title="教材知识点练习",
        description="从探索入口启动教材知识点练习任务。",
        task_type="practice_knowledge_point",
        target_type="knowledge_point",
        default_difficulty="easy",
        estimated_minutes=8,
        required_tools=["rag.retrieve", "exercise.grade", "mastery.update", "memory.write"],
        produces=["attempt", "memory_event", "mastery_update", "review_schedule"],
        metadata={"entrypoint": "explore"},
    ),
}


@skills_router.get("/skills", response_model=list[ExploreSkillSpec])
async def list_explore_skills() -> list[ExploreSkillSpec]:
    return list(EXPLORE_SKILLS.values())


@skills_router.post("/skills/{skill_id}/start")
async def start_explore_skill(
    skill_id: str,
    body: StartExploreSkillRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_learner_exists(db, body.learner_id)
    spec = EXPLORE_SKILLS.get(skill_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Explore skill not found")
    target_id = body.target_id or f"explore:{skill_id}"
    task_spec = TaskSpec(
        task_id=f"explore:{skill_id}:{uuid.uuid4().hex[:12]}",
        task_type=spec.task_type,
        source="explore",
        objective=spec.title,
        target=TaskTarget(
            target_type=spec.target_type or "explore_skill",
            target_id=target_id,
            label=spec.title,
            metadata={"skill_id": skill_id, **body.metadata},
        ),
        difficulty=body.difficulty or spec.default_difficulty,
        allowed_tools=spec.required_tools,
        success_criteria=SuccessCriteria(min_accuracy=0.8, requires_explanation=True),
        verification_policy=VerificationPolicy(
            required_checks=["episode_started"],
            require_evidence=False,
        ),
        metadata={"skill_id": skill_id, "produces": spec.produces, **body.metadata},
    )
    started = await LearningOrchestrator(db).start_task(
        learner_id=body.learner_id,
        task_spec=task_spec,
        recommendation_reason=f"Explore skill: {spec.title}",
    )
    return {
        "episode_id": started.episode_id,
        "task_spec": started.task_spec.model_dump(mode="json") if started.task_spec else None,
        "status": started.status,
        "answer_required": started.answer_required,
        "prompt": started.prompt,
        "initial_payload": started.initial_payload,
    }
