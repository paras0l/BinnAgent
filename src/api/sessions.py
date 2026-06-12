import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.graph.main_graph import daily_lesson_graph
from src.models.session import LearningSession

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    learner_id: str
    user_message: str = "开始今日课程"


class SessionDetailResponse(BaseModel):
    id: uuid.UUID
    status: str
    active_skill: str | None = None
    today_goal: str | None = None
    messages: list[dict] = []
    feedback: dict | None = None
    review_items: list[dict] = []
    input_materials: list[dict] = []


@router.post("/start", response_model=SessionDetailResponse)
async def start_session(
    req: StartSessionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SessionDetailResponse:
    learner_id = uuid.UUID(req.learner_id)
    session = LearningSession(
        learner_id=learner_id,
        session_type="daily_lesson",
        status="active",
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

    result = await daily_lesson_graph.ainvoke(initial_state)

    session.active_skill = result.get("active_skill")
    session.today_goal = result.get("today_goal")
    session.status = "completed"
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
