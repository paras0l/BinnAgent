import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from json import dumps
import logging
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_model_router
from src.agents.vocabulary_agent import (
    VOCABULARY_AGENT_NAME,
    VocabularyAgentResult,
    VocabularyAgentService,
)
from src.agents.skills import AgentSkill, apply_skill_to_metadata, resolve_effective_skill
from src.config import settings
from src.db import async_session_factory
from src.memory.extraction import MemoryExtractionService
from src.memory.layers import MemoryLayer
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryContext, RetrievedMemoryItem
from src.models.learning_progress import LearningProgressItem
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage
from src.models.vocabulary import VocabularyAttempt, VocabularyItem
from src.prompts import prompt_registry
from src.providers.base import ChatRequest as ModelChatRequest
from src.providers.router import ModelRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    learner_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    thread_id: uuid.UUID | None = None
    skill_focus: str | None = Field(default=None, max_length=50)
    skill_id: str | None = Field(default=None, max_length=100)

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
    skill_id: str | None = None
    skill_name: str | None = None
    skill_events: list[dict[str, Any]] = Field(default_factory=list)


TUTOR_SYSTEM_PROMPT = prompt_registry.render(
    prompt_id="tutor.chat",
    version="v1",
    variables={},
).prompt


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
    skill: AgentSkill | None = None,
    memory_context: MemoryContext | None = None,
    max_tokens: int | None = None,
    continuation_text: str | None = None,
) -> ModelChatRequest:
    system_msg = TUTOR_SYSTEM_PROMPT
    if skill is not None:
        system_msg += f"\n\n当前 Agent Skill: {skill.name}\n{skill.system_prompt_patch}"
    elif req.skill_focus:
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
    if memory_context is not None:
        prompt_text = memory_context.prompt_text()
        if prompt_text:
            messages.append({"role": "system", "content": prompt_text})

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

    model_request = ModelChatRequest(
        messages=messages,
        task_type="learning_chat",
        temperature=0.7,
        max_tokens=max_tokens or settings.chat_max_tokens,
    )
    model_request.metadata = {
        **(getattr(model_request, "metadata", None) or {}),
        "prompt_id": "tutor.chat",
        "prompt_version": "v1",
    }
    return model_request


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
    skill: AgentSkill | None,
    memory_context: MemoryContext | None,
) -> tuple[str, str, int]:
    response = await model_router.chat(
        _model_request(req, thread, history, skill=skill, memory_context=memory_context)
    )
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
                skill=skill,
                memory_context=memory_context,
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
    skill: AgentSkill | None,
    memory_context: MemoryContext | None,
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
                skill_focus=_skill_focus_value(skill, req),
                metadata_={"memory_context": _memory_context_metadata(memory_context)},
            )
            db.add(assistant_message)
            await db.flush()
            await _capture_chat_memory_safely(
                db=db,
                req=req,
                thread_id=thread.id,
                assistant_reply=assistant_reply,
                assistant_message_id=assistant_message.id,
                skill=skill,
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> ChatResponse:
    thread = await _get_or_create_thread(req, db)
    skill = _resolve_skill(req, thread)
    if skill is not None:
        thread.metadata_ = apply_skill_to_metadata(thread.metadata_, skill)
    history = await _conversation_history(req, db, thread)
    memory_context = await _retrieve_memory_context_safely(
        db,
        learner_id=req.learner_id,
        reason="chat",
        skill_focus=_skill_focus_value(skill, req),
        thread_id=thread.id,
    )

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
        skill_focus=_skill_focus_value(skill, req),
        metadata_={"memory_context": _memory_context_metadata(memory_context)},
    )
    db.add(user_message)
    await db.flush()

    try:
        reply, finish_reason, continuation_count = await _complete_non_streaming(
            req, thread, history, model_router, skill, memory_context
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Ollama service unavailable")

    assistant_message = ConversationMessage(
        learner_id=req.learner_id,
        thread_id=thread.id,
        role="assistant",
        content=reply,
        sequence=user_message.sequence + 1,
        skill_focus=_skill_focus_value(skill, req),
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
        skill=skill,
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
    skill_events: list[dict[str, Any]] = []
    if _should_trigger_vocabulary_agent(skill):
        skill_events.append(_skill_event("started", skill=skill))
        background_tasks.add_task(
            _run_vocabulary_agent_background,
            req=req,
            thread_id=thread.id,
            assistant_reply=reply,
            assistant_message_id=assistant_message.id,
            model_router=model_router,
        )

    return ChatResponse(
        reply=reply,
        response=reply,
        thread_id=thread.id,
        message_id=assistant_message.id,
        finish_reason=finish_reason,
        continuation_count=continuation_count,
        skill_focus=_skill_focus_value(skill, req),
        skill_id=skill.id if skill else None,
        skill_name=skill.name if skill else None,
        skill_events=skill_events,
    )


async def _capture_chat_memory_safely(
    *,
    db: AsyncSession,
    req: ChatRequest,
    thread_id: uuid.UUID,
    assistant_reply: str,
    assistant_message_id: uuid.UUID | None,
    skill: AgentSkill | None,
) -> None:
    try:
        await MemoryExtractionService(db).capture_chat_turn(
            learner_id=req.learner_id,
            user_message=req.message,
            assistant_reply=assistant_reply,
            thread_id=thread_id,
            assistant_message_id=assistant_message_id,
            skill_focus=_skill_focus_value(skill, req),
        )
    except Exception:
        logger.exception("Failed to capture chat memory")


def _resolve_skill(req: ChatRequest, thread: AgentThread) -> AgentSkill | None:
    return resolve_effective_skill(
        explicit_skill_id=req.skill_id,
        legacy_skill_focus=req.skill_focus,
        thread_metadata=thread.metadata_,
        user_message=req.message,
    )


def _skill_focus_value(skill: AgentSkill | None, req: ChatRequest) -> str | None:
    if skill is not None:
        return skill.id
    return req.skill_focus


def _should_trigger_vocabulary_agent(skill: AgentSkill | None) -> bool:
    return skill is not None and skill.agent_name == VOCABULARY_AGENT_NAME


def _memory_context_metadata(memory_context: MemoryContext | None) -> dict[str, Any]:
    if memory_context is None:
        return {"loaded_items": [], "excluded_items": [], "retrieval_reason": "unknown"}
    return {
        "loaded_items": [item.id for item in memory_context.loaded_items],
        "loaded_item_layers": [item.layer for item in memory_context.loaded_items],
        "context_layer": memory_context.layer,
        "excluded_items": memory_context.excluded_items,
        "retrieval_reason": memory_context.retrieval_reason,
        "token_cost": len(memory_context.prompt_text()),
    }


async def _retrieve_memory_context_safely(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    reason: str,
    skill_focus: str | None,
    thread_id: uuid.UUID,
) -> MemoryContext:
    try:
        context = await MemoryRetriever(db).for_chat(
            learner_id=learner_id,
            skill=skill_focus,
            thread_id=thread_id,
            limit=6,
        )
        try:
            snapshot = await _learning_snapshot_item(db, learner_id=learner_id)
        except Exception:
            logger.exception("Failed to retrieve chat learning snapshot")
            snapshot = None
        if snapshot is not None:
            return MemoryContext(
                loaded_items=[snapshot, *context.loaded_items],
                excluded_items=context.excluded_items,
                retrieval_reason=context.retrieval_reason,
                layer=context.layer,
            )
        return context
    except Exception:
        logger.exception("Failed to retrieve chat memory context")
        return MemoryContext(loaded_items=[], excluded_items=[], retrieval_reason=reason)


async def _learning_snapshot_item(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
) -> RetrievedMemoryItem | None:
    total_vocab_result = await db.execute(
        select(func.count()).select_from(VocabularyItem).where(VocabularyItem.learner_id == learner_id)
    )
    mastered_vocab_result = await db.execute(
        select(func.count())
        .select_from(VocabularyItem)
        .where(VocabularyItem.learner_id == learner_id, VocabularyItem.status == "mastered")
    )
    recent_attempt_result = await db.execute(
        select(VocabularyAttempt, VocabularyItem.word)
        .join(VocabularyItem, VocabularyItem.id == VocabularyAttempt.vocabulary_item_id)
        .where(VocabularyAttempt.learner_id == learner_id)
        .order_by(VocabularyAttempt.occurred_at.desc())
        .limit(12)
    )
    grammar_count_result = await db.execute(
        select(func.count())
        .select_from(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "grammar",
            LearningProgressItem.status == "learned",
        )
    )
    grammar_result = await db.execute(
        select(LearningProgressItem)
        .where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "grammar",
            LearningProgressItem.status == "learned",
        )
        .order_by(
            LearningProgressItem.learned_at.desc().nullslast(),
            LearningProgressItem.updated_at.desc(),
        )
        .limit(12)
    )

    total_vocab = int(total_vocab_result.scalar_one() or 0)
    mastered_vocab = int(mastered_vocab_result.scalar_one() or 0)
    grammar_count = int(grammar_count_result.scalar_one() or 0)
    recent_attempts = recent_attempt_result.all()
    recent_words = _unique_texts(str(word) for _, word in recent_attempts if word)
    grammar_titles = _unique_texts(
        item.title for item in grammar_result.scalars().all() if item.title
    )

    if total_vocab == 0 and grammar_count == 0 and not recent_words:
        return None

    parts = [f"学习快照：词汇库共 {total_vocab} 个词，已掌握 {mastered_vocab} 个。"]
    if recent_attempts:
        parts.append(
            f"最近词汇练习 {len(recent_attempts)} 次，涉及 {len(recent_words)} 个词："
            f"{_join_preview(recent_words)}。"
        )
    if grammar_count:
        parts.append(f"已学语法 {grammar_count} 个：{_join_preview(grammar_titles)}。")
    parts.append("回答用户学习盘点问题时，优先使用这些结构化数字；如果只列出部分项目，要说明这是最近/前若干条记录。")

    return RetrievedMemoryItem(
        id="learning_snapshot:current",
        type="learning_snapshot",
        skill="general",
        summary=" ".join(parts),
        confidence=1.0,
        layer=MemoryLayer.CONTEXT.value,
        reason="structured_learning_progress",
        payload={
            "total_vocab": total_vocab,
            "mastered_vocab": mastered_vocab,
            "recent_vocabulary_attempt_count": len(recent_attempts),
            "recent_words": recent_words,
            "grammar_learned": grammar_count,
            "recent_grammar_titles": grammar_titles,
        },
    )


def _unique_texts(values: Any) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items


def _join_preview(values: list[str], *, limit: int = 12) -> str:
    if not values:
        return "暂无明细"
    preview = "、".join(values[:limit])
    if len(values) > limit:
        preview += f"等 {len(values)} 项"
    return preview


def _skill_event(
    status: str,
    *,
    skill: AgentSkill | None,
    saved_count: int | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "name": skill.agent_name if skill else VOCABULARY_AGENT_NAME,
        "skill_id": skill.id if skill else None,
        "skill_name": skill.name if skill else None,
        "status": status,
    }
    if skill is not None:
        template = skill.status_messages.get(status)
        if template:
            event["message"] = template.format(saved_count=saved_count or 0)
    if saved_count is not None:
        event["saved_count"] = saved_count
    return event


async def _run_vocabulary_agent_background(
    *,
    req: ChatRequest,
    thread_id: uuid.UUID,
    assistant_reply: str,
    assistant_message_id: uuid.UUID | None,
    model_router: ModelRouter,
) -> VocabularyAgentResult:
    async with async_session_factory() as db:
        try:
            result = await VocabularyAgentService(db, model_router).capture_chat_turn(
                learner_id=req.learner_id,
                user_message=req.message,
                assistant_reply=assistant_reply,
                source_ref=f"conversation_message:{assistant_message_id}"
                if assistant_message_id
                else f"thread:{thread_id}",
            )
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            logger.exception("Failed to run vocabulary agent")
            return VocabularyAgentResult(failed=True)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> StreamingResponse:
    thread = await _get_or_create_thread(req, db)
    skill = _resolve_skill(req, thread)
    if skill is not None:
        thread.metadata_ = apply_skill_to_metadata(thread.metadata_, skill)
    history = await _conversation_history(req, db, thread)
    memory_context = await _retrieve_memory_context_safely(
        db,
        learner_id=req.learner_id,
        reason="chat_stream",
        skill_focus=_skill_focus_value(skill, req),
        thread_id=thread.id,
    )

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
        skill_focus=_skill_focus_value(skill, req),
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
        yield _sse_event(
            "meta",
            {
                "thread_id": str(thread_id),
                "skill_id": skill.id if skill else None,
                "skill_name": skill.name if skill else None,
                "skill_focus": _skill_focus_value(skill, req),
            },
        )

        try:
            while True:
                request = _model_request(
                    req,
                    thread,
                    history,
                    skill=skill,
                    memory_context=memory_context,
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
                skill=skill,
                memory_context=memory_context,
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
                "skill_id": skill.id if skill else None,
                "skill_name": skill.name if skill else None,
            },
        )

        if _should_trigger_vocabulary_agent(skill):
            yield _sse_event("skill", _skill_event("started", skill=skill))
            result = await _run_vocabulary_agent_background(
                req=req,
                thread_id=thread_id,
                assistant_reply=reply,
                assistant_message_id=assistant_message.id,
                model_router=model_router,
            )
            if result.failed:
                yield _sse_event("skill", _skill_event("failed", skill=skill))
            elif result.saved_count > 0:
                yield _sse_event(
                    "skill",
                    _skill_event("completed", skill=skill, saved_count=result.saved_count),
                )
            else:
                yield _sse_event("skill", _skill_event("skipped", skill=skill, saved_count=0))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
