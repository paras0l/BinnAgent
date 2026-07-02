import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.learning.orchestrator import LearningOrchestrator
from src.learning.types import LearningPlanRequest, StartedTask

router = APIRouter(prefix="/api/learners/{learner_id}/daily-lessons", tags=["daily-lessons"])


class DailyLessonStartRequest(BaseModel):
    current_curriculum_node_id: uuid.UUID | None = None
    time_budget_minutes: int | None = Field(default=None, ge=1, le=240)
    mode_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DailyLessonAnswerRequest(BaseModel):
    answer: str | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/start", response_model=StartedTask)
async def start_daily_lesson(
    learner_id: uuid.UUID,
    body: DailyLessonStartRequest | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> StartedTask:
    body = body or DailyLessonStartRequest()
    orchestrator = LearningOrchestrator(db)
    plan = await orchestrator.build_learning_plan(
        LearningPlanRequest(
            learner_id=str(learner_id),
            current_curriculum_node_id=(
                str(body.current_curriculum_node_id) if body.current_curriculum_node_id else None
            ),
            time_budget_minutes=body.time_budget_minutes,
            mode_hint=body.mode_hint,
            metadata=body.metadata,
        )
    )
    if plan.selected_task is None:
        return StartedTask(
            episode_id="",
            task_spec=None,
            status="empty",
            answer_required=False,
            prompt=None,
            initial_payload={"reason": plan.reason},
            recommendation_reason=plan.reason,
        )
    return await orchestrator.start_task(
        learner_id=learner_id,
        task_spec=plan.selected_task,
        recommendation_reason=plan.reason,
    )


@router.post("/{episode_id}/answer")
async def submit_daily_lesson_answer(
    learner_id: uuid.UUID,
    episode_id: uuid.UUID,
    body: DailyLessonAnswerRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await LearningOrchestrator(db).submit_answer(
        learner_id=learner_id,
        episode_id=episode_id,
        answer=body.answer,
        metadata=body.metadata,
    )


@router.get("/{episode_id}")
async def get_daily_lesson_status(
    learner_id: uuid.UUID,
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await LearningOrchestrator(db).get_daily_lesson_status(
        learner_id=learner_id,
        episode_id=episode_id,
    )
