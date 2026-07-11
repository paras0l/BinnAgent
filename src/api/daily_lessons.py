import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_learner, get_db_session, get_model_router
from src.learning.orchestrator import LearningOrchestrator
from src.learning.types import LearningPlanRequest, StartedTask
from src.models.learner import Learner
from src.providers.router import ModelRouter
from src.classroom.service import (
    ClassroomNotFoundError,
    audio_path,
    coach_textbook_task,
    compose_classroom,
    save_classroom_progress,
    timeline_payload,
)
from src.classroom.catalog import exercise_asset_path

router = APIRouter(prefix="/api/learners/{learner_id}/daily-lessons", tags=["daily-lessons"])


class DailyLessonStartRequest(BaseModel):
    current_curriculum_node_id: uuid.UUID | None = None
    time_budget_minutes: int | None = Field(default=None, ge=1, le=240)
    mode_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DailyLessonAnswerRequest(BaseModel):
    answer: str | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassroomComposeRequest(BaseModel):
    curriculum_node_id: uuid.UUID
    time_budget_minutes: int = Field(default=20, ge=5, le=90)


class ClassroomProgressRequest(BaseModel):
    curriculum_node_id: uuid.UUID
    classroom_id: str = Field(min_length=1, max_length=200)
    current_phase_id: str = Field(min_length=1, max_length=40)
    completed_phase_ids: list[str] = Field(default_factory=list, max_length=12)
    flipped_card_ids: list[str] = Field(default_factory=list, max_length=12)
    listened_cue_ids: list[str] = Field(default_factory=list, max_length=240)
    textbook_task_answers: dict[str, str] = Field(default_factory=dict)
    grammar_answers: dict[str, str] = Field(default_factory=dict)
    grammar_transfer: str = Field(default="", max_length=2000)
    completed: bool = False


class ClassroomCoachRequest(BaseModel):
    curriculum_node_id: uuid.UUID
    task_id: str = Field(min_length=1, max_length=80)
    answer: str = Field(min_length=1, max_length=4000)


@router.post("/classroom/compose")
async def compose_daily_classroom(
    learner_id: uuid.UUID,
    body: ClassroomComposeRequest,
    current_learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    try:
        return await compose_classroom(
            db, model_router, learner_id=current_learner.id,
            curriculum_node_id=body.curriculum_node_id,
            time_budget_minutes=body.time_budget_minutes,
        )
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/classroom/coach")
async def coach_daily_classroom_task(
    learner_id: uuid.UUID,
    body: ClassroomCoachRequest,
    current_learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    try:
        return await coach_textbook_task(
            db,
            model_router,
            learner_id=current_learner.id,
            curriculum_node_id=body.curriculum_node_id,
            task_id=body.task_id,
            answer=body.answer,
        )
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/classroom/progress")
async def update_daily_classroom_progress(
    learner_id: uuid.UUID,
    body: ClassroomProgressRequest,
    current_learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        return await save_classroom_progress(
            db,
            learner_id=current_learner.id,
            curriculum_node_id=body.curriculum_node_id,
            classroom_id=body.classroom_id,
            current_phase_id=body.current_phase_id,
            completed_phase_ids=body.completed_phase_ids,
            flipped_card_ids=body.flipped_card_ids,
            listened_cue_ids=body.listened_cue_ids,
            textbook_task_answers=body.textbook_task_answers,
            grammar_answers=body.grammar_answers,
            grammar_transfer=body.grammar_transfer,
            completed=body.completed,
        )
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/classroom/audio/{track}")
async def get_classroom_audio(
    learner_id: uuid.UUID,
    track: str,
    _current_learner: Learner = Depends(get_current_learner),
) -> FileResponse:
    try:
        path = audio_path(track)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/mpeg", filename=track)


@router.get("/classroom/timeline/{track}")
async def get_classroom_timeline(
    learner_id: uuid.UUID,
    track: str,
    _current_learner: Learner = Depends(get_current_learner),
) -> dict[str, Any]:
    try:
        payload = timeline_payload(track)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="reviewed timeline is not available yet")
    return payload


@router.get("/classroom/textbook-task/{asset}")
async def get_classroom_textbook_task(
    learner_id: uuid.UUID,
    asset: str,
    _current_learner: Learner = Depends(get_current_learner),
) -> FileResponse:
    try:
        path = exercise_asset_path(asset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="textbook task asset not found") from exc
    return FileResponse(path, media_type="image/webp", filename=asset)


@router.post("/start", response_model=StartedTask)
async def start_daily_lesson(
    learner_id: uuid.UUID,
    body: DailyLessonStartRequest | None = None,
    _current_learner: Learner = Depends(get_current_learner),
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
    _current_learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> dict[str, Any]:
    return await LearningOrchestrator(db, model_router=model_router).submit_answer(
        learner_id=learner_id,
        episode_id=episode_id,
        answer=body.answer,
        metadata=body.metadata,
    )


@router.get("/{episode_id}")
async def get_daily_lesson_status(
    learner_id: uuid.UUID,
    episode_id: uuid.UUID,
    _current_learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await LearningOrchestrator(db).get_daily_lesson_status(
        learner_id=learner_id,
        episode_id=episode_id,
    )
