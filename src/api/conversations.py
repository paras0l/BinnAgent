import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.agents.skills import clear_skill_from_metadata
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage

router = APIRouter(
    prefix="/api/learners/{learner_id}/conversations",
    tags=["conversations"],
)


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    sequence: int
    skill_focus: str | None = None
    created_at: datetime


class LatestConversationResponse(BaseModel):
    thread_id: uuid.UUID | None = None
    skill_id: str | None = None
    skill_name: str | None = None
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationThreadResponse(BaseModel):
    thread_id: uuid.UUID
    title: str
    last_message: str | None = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    skill_id: str | None = None
    skill_name: str | None = None


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


async def _get_owned_thread(
    db: AsyncSession,
    learner_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> AgentThread:
    result = await db.execute(
        select(AgentThread).where(
            AgentThread.id == thread_id,
            AgentThread.learner_id == learner_id,
        )
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation thread not found")
    return thread


@router.get("/latest", response_model=LatestConversationResponse)
async def get_latest_conversation(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> LatestConversationResponse:
    await _ensure_learner_exists(db, learner_id)
    threads = await _list_threads(db, learner_id)
    thread = threads[0] if threads else None
    if thread is None:
        return LatestConversationResponse()

    messages = await _list_thread_messages(db, learner_id, thread.id)
    metadata = thread.metadata_ or {}
    return LatestConversationResponse(
        thread_id=thread.id,
        skill_id=metadata.get("skill_id") if isinstance(metadata.get("skill_id"), str) else None,
        skill_name=metadata.get("skill_name") if isinstance(metadata.get("skill_name"), str) else None,
        messages=messages,
    )


@router.get("", response_model=list[ConversationThreadResponse])
async def list_conversations(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ConversationThreadResponse]:
    await _ensure_learner_exists(db, learner_id)
    threads = await _list_threads(db, learner_id)
    responses: list[ConversationThreadResponse] = []

    for thread in threads:
        messages = await _list_thread_messages(db, learner_id, thread.id)
        if not messages:
            continue
        responses.append(_thread_response(thread, messages))

    return responses


@router.get("/{thread_id}/messages", response_model=list[ConversationMessageResponse])
async def get_conversation_messages(
    learner_id: uuid.UUID,
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ConversationMessage]:
    await _ensure_learner_exists(db, learner_id)
    await _get_owned_thread(db, learner_id, thread_id)
    return await _list_thread_messages(db, learner_id, thread_id)


@router.delete("/{thread_id}/skill", status_code=204)
async def exit_conversation_skill(
    learner_id: uuid.UUID,
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _ensure_learner_exists(db, learner_id)
    thread = await _get_owned_thread(db, learner_id, thread_id)
    thread.metadata_ = clear_skill_from_metadata(thread.metadata_)
    await db.flush()


async def _list_threads(db: AsyncSession, learner_id: uuid.UUID) -> list[AgentThread]:
    result = await db.execute(
        select(AgentThread)
        .where(AgentThread.learner_id == learner_id)
        .order_by(AgentThread.updated_at.desc(), AgentThread.created_at.desc())
    )
    threads = list(result.scalars().all())
    return sorted(threads, key=_thread_activity_key, reverse=True)


def _thread_activity_key(thread: AgentThread) -> datetime:
    metadata = thread.metadata_ or {}
    last_message_at = metadata.get("last_message_at")
    if isinstance(last_message_at, str):
        try:
            return datetime.fromisoformat(last_message_at)
        except ValueError:
            pass
    return thread.updated_at or thread.created_at or datetime.min.replace(tzinfo=timezone.utc)


def _thread_response(
    thread: AgentThread,
    messages: list[ConversationMessage],
) -> ConversationThreadResponse:
    metadata = thread.metadata_ or {}
    first_user = next((message.content for message in messages if message.role == "user"), "")
    title = metadata.get("title") if isinstance(metadata.get("title"), str) else ""
    last_message = messages[-1].content if messages else None
    return ConversationThreadResponse(
        thread_id=thread.id,
        title=title.strip() or first_user.strip().replace("\n", " ")[:40] or "新对话",
        last_message=last_message.strip().replace("\n", " ")[:80] if last_message else None,
        message_count=len(messages),
        created_at=thread.created_at,
        updated_at=_thread_activity_key(thread),
        skill_id=metadata.get("skill_id") if isinstance(metadata.get("skill_id"), str) else None,
        skill_name=metadata.get("skill_name") if isinstance(metadata.get("skill_name"), str) else None,
    )


async def _list_thread_messages(
    db: AsyncSession,
    learner_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> list[ConversationMessage]:
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.learner_id == learner_id,
            ConversationMessage.thread_id == thread_id,
        )
        .order_by(ConversationMessage.sequence.asc())
    )
    return list(result.scalars().all())
