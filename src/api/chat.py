import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from json import dumps
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_model_router
from src.config import settings
from src.db import async_session_factory
from src.memory.extraction import MemoryExtractionService
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage
from src.providers.base import ChatRequest as ModelChatRequest
from src.providers.router import ModelRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    learner_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    thread_id: uuid.UUID | None = None
    skill_focus: str | None = Field(default=None, max_length=50)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message must not be blank")
        return stripped


class ChatResponse(BaseModel):
    reply: str
    response: str
    thread_id: uuid.UUID
    message_id: uuid.UUID
    finish_reason: str = "stop"
    continuation_count: int = 0
    skill_focus: str | None = None


TUTOR_SYSTEM_PROMPT = """你是BinnAgent，一位专业的英语学习AI助教。你的职责是帮助学员提高英语水平，特别是针对CET-4和CET-6考试。

你的特点：
- 用中文与学员交流，但会穿插英语例句和解释
- 耐心、鼓励、专业
- 能解释词汇、语法、阅读理解、写作技巧
- 会根据学员水平调整难度
- 主动提问检验学员理解程度

请用简洁友好的方式回复学员的问题。如果学员问的是英语学习相关的问题，请用中英文结合的方式回答。"""


async def _get_or_create_thread(
    req: ChatRequest,
    db: AsyncSession,
) -> AgentThread:
    learner_result = await db.execute(select(Learner.id).where(Learner.id == req.learner_id))
    if learner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    if req.thread_id:
        thread_result = await db.execute(
            select(AgentThread).where(
                AgentThread.id == req.thread_id,
                AgentThread.learner_id == req.learner_id,
            )
        )
        thread = thread_result.scalar_one_or_none()
        if thread is None:
            raise HTTPException(status_code=404, detail="Conversation thread not found")
        return thread

    thread = AgentThread(
        learner_id=req.learner_id,
        status="active",
        metadata_={"source": "chat"},
    )
    db.add(thread)
    await db.flush()
    return thread


async def _conversation_history(
    req: ChatRequest,
    db: AsyncSession,
    thread: AgentThread,
) -> list[ConversationMessage]:
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.learner_id == req.learner_id,
            ConversationMessage.thread_id == thread.id,
        )
        .order_by(ConversationMessage.sequence.desc())
        .limit(settings.chat_history_limit)
    )
    return list(reversed(result.scalars().all()))


async def _next_message_sequence(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> int:
    result = await db.execute(
        select(func.max(ConversationMessage.sequence)).where(
            ConversationMessage.learner_id == learner_id,
            ConversationMessage.thread_id == thread_id,
        )
    )
    current_max = result.scalar_one_or_none()
    return int(current_max or 0) + 1


def _model_request(
    req: ChatRequest,
    thread: AgentThread,
    history: list[ConversationMessage],
    *,
    max_tokens: int | None = None,
    continuation_text: str | None = None,
) -> ModelChatRequest:
    system_msg = TUTOR_SYSTEM_PROMPT
    if req.skill_focus:
        system_msg += f"\n\n当前重点练习: {req.skill_focus}"

    messages = [{"role": "system", "content": system_msg}]
    metadata = thread.metadata_ or {}
    summary = metadata.get("summary")
    if isinstance(summary, str) and summary.strip():
        messages.append(
            {
                "role": "system",
                "content": f"此前对话摘要：\n{summary.strip()}",
            }
        )

    messages.extend({"role": message.role, "content": message.content} for message in history)
    if continuation_text:
        messages.append({"role": "user", "content": req.message})
        messages.append(
            {
                "role": "assistant",
                "content": continuation_text,
            }
        )
        messages.append(
            {
                "role": "user",
                "content": "上一段回答因长度限制中断，请从中断处自然继续，不要重复已回答内容。",
            }
        )
    else:
        messages.append({"role": "user", "content": req.message})

    return ModelChatRequest(
        messages=messages,
        task_type="learning_chat",
        temperature=0.7,
        max_tokens=max_tokens or settings.chat_max_tokens,
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {dumps(data, ensure_ascii=False)}\n\n"


def _touch_thread(thread: AgentThread, user_message: str) -> None:
    metadata = thread.metadata_ or {}
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        title = user_message.strip().replace("\n", " ")[:40] or "新对话"

    thread.metadata_ = {
        **metadata,
        "title": title,
        "last_message_at": datetime.now(timezone.utc).isoformat(),
    }


def _chunk_content_and_finish(chunk: Any) -> tuple[str, str | None]:
    if isinstance(chunk, str):
        return chunk, None
    return getattr(chunk, "content", "") or "", getattr(chunk, "finish_reason", None)


async def _complete_non_streaming(
    req: ChatRequest,
    thread: AgentThread,
    history: list[ConversationMessage],
    model_router: ModelRouter,
) -> tuple[str, str, int]:
    response = await model_router.chat(_model_request(req, thread, history))
    reply_parts = [response.content]
    finish_reason = response.finish_reason
    continuation_count = 0

    while finish_reason == "length" and continuation_count < settings.chat_auto_continue_limit:
        continuation_count += 1
        response = await model_router.chat(
            _model_request(
                req,
                thread,
                history,
                continuation_text="".join(reply_parts),
            )
        )
        reply_parts.append(response.content)
        finish_reason = response.finish_reason

    return "".join(reply_parts) or "抱歉，我暂时无法回复。", finish_reason, continuation_count


async def _maybe_update_thread_summary(
    *,
    db: AsyncSession,
    req: ChatRequest,
    thread: AgentThread,
    history: list[ConversationMessage],
    assistant_reply: str,
    model_router: ModelRouter,
) -> None:
    if len(history) + 2 <= settings.chat_history_limit:
        return

    existing_summary = ""
    metadata = thread.metadata_ or {}
    if isinstance(metadata.get("summary"), str):
        existing_summary = metadata["summary"]

    transcript = "\n".join(
        [f"{message.role}: {message.content}" for message in history]
        + [f"user: {req.message}", f"assistant: {assistant_reply}"]
    )
    summary_prompt = (
        "请为英语学习陪伴对话更新一段紧凑摘要，保留后续续写和教学最需要的信息："
        "用户问题、assistant已回答要点、未完成部分、学习目标、术语约定。"
        "不要超过300字。\n\n"
        f"已有摘要：{existing_summary or '无'}\n\n最新对话：\n{transcript}"
    )
    try:
        response = await model_router.chat(
            ModelChatRequest(
                messages=[
                    {"role": "system", "content": "你是对话记忆摘要器，只输出摘要正文。"},
                    {"role": "user", "content": summary_prompt},
                ],
                task_type="conversation_summary",
                temperature=0.2,
                max_tokens=512,
                preferred_model=None,
            )
        )
    except httpx.HTTPError:
        return

    summary = response.content.strip()
    if not summary:
        return
    thread.metadata_ = {
        **metadata,
        "summary": summary,
        "summary_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.flush()


async def _persist_stream_assistant_message(
    *,
    req: ChatRequest,
    thread_id: uuid.UUID,
    history: list[ConversationMessage],
    assistant_reply: str,
    model_router: ModelRouter,
) -> ConversationMessage:
    async with async_session_factory() as db:
        try:
            thread_result = await db.execute(
                select(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.learner_id == req.learner_id,
                )
            )
            thread = thread_result.scalar_one_or_none()
            if thread is None:
                raise ValueError("Conversation thread not found")

            assistant_message = ConversationMessage(
                learner_id=req.learner_id,
                thread_id=thread.id,
                role="assistant",
                content=assistant_reply,
                sequence=await _next_message_sequence(
                    db,
                    learner_id=req.learner_id,
                    thread_id=thread.id,
                ),
                skill_focus=req.skill_focus,
                metadata_={},
            )
            db.add(assistant_message)
            await db.flush()
            await _capture_chat_memory_safely(
                db=db,
                req=req,
                thread_id=thread.id,
                assistant_reply=assistant_reply,
                assistant_message_id=assistant_message.id,
            )
            _touch_thread(thread, req.message)
            await _maybe_update_thread_summary(
                db=db,
                req=req,
                thread=thread,
                history=history,
                assistant_reply=assistant_reply,
                model_router=model_router,
            )
            await db.commit()
            await db.refresh(assistant_message)
            return assistant_message
        except Exception:
            await db.rollback()
            raise


@router.post("/send", response_model=ChatResponse)
async def chat_send(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> ChatResponse:
    thread = await _get_or_create_thread(req, db)
    history = await _conversation_history(req, db, thread)

    user_message = ConversationMessage(
        learner_id=req.learner_id,
        thread_id=thread.id,
        role="user",
        content=req.message,
        sequence=await _next_message_sequence(
            db,
            learner_id=req.learner_id,
            thread_id=thread.id,
        ),
        skill_focus=req.skill_focus,
        metadata_={},
    )
    db.add(user_message)
    await db.flush()

    try:
        reply, finish_reason, continuation_count = await _complete_non_streaming(
            req, thread, history, model_router
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Ollama service unavailable")

    assistant_message = ConversationMessage(
        learner_id=req.learner_id,
        thread_id=thread.id,
        role="assistant",
        content=reply,
        sequence=user_message.sequence + 1,
        skill_focus=req.skill_focus,
        metadata_={},
    )
    db.add(assistant_message)
    await db.flush()
    await _capture_chat_memory_safely(
        db=db,
        req=req,
        thread_id=thread.id,
        assistant_reply=reply,
        assistant_message_id=assistant_message.id,
    )
    _touch_thread(thread, req.message)
    await _maybe_update_thread_summary(
        db=db,
        req=req,
        thread=thread,
        history=history,
        assistant_reply=reply,
        model_router=model_router,
    )
    await db.commit()
    await db.refresh(assistant_message)

    return ChatResponse(
        reply=reply,
        response=reply,
        thread_id=thread.id,
        message_id=assistant_message.id,
        finish_reason=finish_reason,
        continuation_count=continuation_count,
        skill_focus=req.skill_focus,
    )


async def _capture_chat_memory_safely(
    *,
    db: AsyncSession,
    req: ChatRequest,
    thread_id: uuid.UUID,
    assistant_reply: str,
    assistant_message_id: uuid.UUID | None,
) -> None:
    try:
        await MemoryExtractionService(db).capture_chat_turn(
            learner_id=req.learner_id,
            user_message=req.message,
            assistant_reply=assistant_reply,
            thread_id=thread_id,
            assistant_message_id=assistant_message_id,
            skill_focus=req.skill_focus,
        )
    except Exception:
        logger.exception("Failed to capture chat memory")


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> StreamingResponse:
    thread = await _get_or_create_thread(req, db)
    history = await _conversation_history(req, db, thread)

    user_message = ConversationMessage(
        learner_id=req.learner_id,
        thread_id=thread.id,
        role="user",
        content=req.message,
        sequence=await _next_message_sequence(
            db,
            learner_id=req.learner_id,
            thread_id=thread.id,
        ),
        skill_focus=req.skill_focus,
        metadata_={},
    )
    db.add(user_message)
    await db.flush()
    _touch_thread(thread, req.message)
    await db.commit()
    thread_id = thread.id

    async def event_stream() -> AsyncIterator[str]:
        chunks: list[str] = []
        finish_reason = "stop"
        continuation_count = 0
        yield _sse_event("meta", {"thread_id": str(thread_id)})

        try:
            while True:
                request = _model_request(
                    req,
                    thread,
                    history,
                    continuation_text="".join(chunks) if continuation_count > 0 else None,
                )
                async for raw_chunk in model_router.stream_chat(request):
                    content, chunk_finish_reason = _chunk_content_and_finish(raw_chunk)
                    if content:
                        chunks.append(content)
                        yield _sse_event("delta", {"content": content})
                    if chunk_finish_reason:
                        finish_reason = chunk_finish_reason

                if (
                    finish_reason != "length"
                    or continuation_count >= settings.chat_auto_continue_limit
                ):
                    break

                continuation_count += 1
                yield _sse_event(
                    "continuation",
                    {
                        "count": continuation_count,
                        "limit": settings.chat_auto_continue_limit,
                    },
                )
        except httpx.HTTPError:
            yield _sse_event("error", {"detail": "Ollama service unavailable"})
            return
        except ValueError:
            yield _sse_event("error", {"detail": "Invalid model stream response"})
            return

        reply = "".join(chunks) or "抱歉，我暂时无法回复。"
        try:
            assistant_message = await _persist_stream_assistant_message(
                req=req,
                thread_id=thread_id,
                history=history,
                assistant_reply=reply,
                model_router=model_router,
            )
        except Exception:
            yield _sse_event("error", {"detail": "Failed to persist conversation memory"})
            return

        yield _sse_event(
            "done",
            {
                "thread_id": str(thread_id),
                "message_id": str(assistant_message.id),
                "reply": reply,
                "finish_reason": finish_reason,
                "continuation_count": continuation_count,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
