import uuid
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.graph.main_graph import daily_lesson_graph
from src.memory.extraction import MemoryExtractionService
from src.models.learner import Learner
from src.models.session import LearningSession

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


class StartSessionRequest(BaseModel):
    learner_id: uuid.UUID
    user_message: str = "开始今日课程"


class SessionDetailResponse(BaseModel):
    id: uuid.UUID
    status: str
    active_skill: str | None = None
    today_goal: str | None = None
    messages: list[dict] = Field(default_factory=list)
    feedback: dict | None = None
    review_items: list[dict] = Field(default_factory=list)
    input_materials: list[dict] = Field(default_factory=list)


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


@router.post("/start", response_model=SessionDetailResponse)
async def start_session(
    req: StartSessionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SessionDetailResponse:
    learner_id = req.learner_id
    await _ensure_learner_exists(db, learner_id)

    session = LearningSession(
        learner_id=learner_id,
        session_type="daily_lesson",
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    initial_state = {
        "user_id": str(learner_id),
        "thread_id": str(uuid.uuid4()),
        "session_id": str(session.id),
        "target_exam": "CET6",
        "daily_time_budget": 30,
        "messages": [{"role": "user", "content": req.user_message}],
    }

    try:
        result = await daily_lesson_graph.ainvoke(initial_state)
    except Exception as exc:
        session.status = "failed"
        session.completed_at = datetime.now(timezone.utc)
        session.summary = str(exc)[:500]
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to start learning session")

    session.active_skill = result.get("active_skill")
    session.today_goal = result.get("today_goal")
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.summary = _session_summary(result)
    try:
        await MemoryExtractionService(db).capture_session_result(
            learner_id=learner_id,
            session_id=session.id,
            result=result,
        )
    except Exception:
        logger.exception("Failed to capture session memory")
    await db.commit()
    await db.refresh(session)

    messages: list[dict] = []
    raw_messages = result.get("messages", [])
    for msg in raw_messages:
        if hasattr(msg, "content"):
            role = getattr(msg, "type", "assistant")
            messages.append({"role": role, "content": msg.content})
        elif isinstance(msg, dict):
            messages.append(msg)

    return SessionDetailResponse(
        id=session.id,
        status=session.status,
        active_skill=session.active_skill,
        today_goal=session.today_goal,
        messages=messages,
        feedback=result.get("agent_feedback"),
        review_items=result.get("review_items", []),
        input_materials=result.get("input_materials", []),
    )


def _session_summary(result: dict) -> str | None:
    today_goal = result.get("today_goal")
    active_skill = result.get("active_skill")
    if today_goal and active_skill:
        return f"{active_skill}: {today_goal}"
    if today_goal:
        return str(today_goal)
    if active_skill:
        return f"Completed {active_skill} practice"
    return None
