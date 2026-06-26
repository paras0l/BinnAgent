import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.error_store import ErrorStore
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.session import LearningSession


_WORD_RE = re.compile(r"\b[a-zA-Z][a-zA-Z'-]{2,24}\b")

_SKILL_KEYWORDS = {
    "vocabulary": ("词汇", "单词", "vocabulary", "word", "meaning", "means"),
    "writing": ("作文", "写作", "essay", "writing", "批改", "润色"),
    "reading": ("阅读", "reading", "passage", "选项", "答案"),
    "grammar": ("语法", "grammar", "时态", "从句", "主谓"),
    "translation": ("翻译", "translate", "translation"),
    "listening": ("听力", "listening"),
    "speaking": ("口语", "speaking"),
}

_ERROR_PATTERNS = (
    ("missing_articles", "writing", ("冠词", "article", "a/an/the"), "冠词使用不稳定"),
    (
        "subject_verb_agreement",
        "writing",
        ("主谓一致", "subject-verb", "subject verb"),
        "主谓一致错误",
    ),
    ("tense_confusion", "writing", ("时态", "tense"), "时态使用不稳定"),
    ("preposition_misuse", "writing", ("介词", "preposition"), "介词搭配错误"),
    ("spelling_error", "writing", ("拼写", "spelling"), "拼写错误"),
    ("word_choice", "writing", ("用词", "word choice", "搭配", "collocation"), "用词或搭配不自然"),
    (
        "transition_signal_missed",
        "reading",
        ("转折", "however", "but", "contrast"),
        "阅读中容易忽略转折信号",
    ),
    ("sentence_structure", "writing", ("句子结构", "sentence structure"), "句子结构需要优化"),
)


@dataclass(frozen=True)
class MemoryExtractionResult:
    error_count: int = 0
    session_created: bool = False


class MemoryExtractionService:
    """Conservative rule-based writer for error memory and learning activity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def capture_chat_turn(
        self,
        *,
        learner_id: uuid.UUID,
        user_message: str,
        assistant_reply: str,
        thread_id: uuid.UUID | None = None,
        assistant_message_id: uuid.UUID | None = None,
        skill_focus: str | None = None,
    ) -> MemoryExtractionResult:
        active_skill = _infer_skill(user_message, assistant_reply, skill_focus)
        error_count = 0

        if _is_evaluable_submission(user_message, active_skill):
            source_ref = _source_ref("conversation_message", assistant_message_id, thread_id)
            for pattern, skill, description in _extract_error_patterns(
                assistant_reply,
                fallback_skill=active_skill,
            ):
                await ErrorStore(self.db).record_error(
                    learner_id=learner_id,
                    skill=skill,
                    pattern=pattern,
                    description=description,
                    evidence_ref=source_ref,
                    commit=False,
                )
                await MemoryWriter(self.db).record_event(
                    MemoryEventInput(
                        learner_id=learner_id,
                        event_type="chat_error_observed",
                        skill=skill,
                        source_type="conversation_message",
                        source_id=str(assistant_message_id or thread_id) if (assistant_message_id or thread_id) else None,
                        thread_id=thread_id,
                        payload={
                            "pattern": pattern,
                            "description": description,
                            "summary": _summarize_chat_learning(user_message, active_skill),
                        },
                        confidence=0.72,
                        created_by="system",
                    )
                )
                error_count += 1

        session_created = False
        if _is_learning_activity(user_message, assistant_reply, active_skill):
            summary = _summarize_chat_learning(user_message, active_skill)
            session = LearningSession(
                learner_id=learner_id,
                thread_id=str(thread_id) if thread_id else None,
                session_type="chat_learning",
                active_skill=active_skill,
                today_goal=summary,
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                summary=summary,
            )
            self.db.add(session)
            await self.db.flush()
            await MemoryWriter(self.db).record_event(
                MemoryEventInput(
                    learner_id=learner_id,
                    event_type="chat_learning_turn",
                    skill=active_skill,
                    source_type="conversation_message",
                    source_id=str(assistant_message_id or thread_id) if (assistant_message_id or thread_id) else None,
                    thread_id=thread_id,
                    session_id=session.id,
                    payload={
                        "summary": summary,
                        "episode_type": "chat_learning",
                        "user_message_preview": user_message[:160],
                    },
                    confidence=0.8,
                    created_by="system",
                )
            )
            session_created = True

        return MemoryExtractionResult(error_count=error_count, session_created=session_created)

    async def capture_session_result(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        result: dict[str, Any],
    ) -> MemoryExtractionResult:
        active_skill = _normalize_skill(result.get("active_skill")) or "general"
        feedback = result.get("agent_feedback") if isinstance(result.get("agent_feedback"), dict) else {}
        error_count = 0

        issue_text = " ".join(
            str(issue)
            for issue in feedback.get("key_issues", [])
            if isinstance(issue, str) and issue.strip()
        )
        if issue_text:
            for pattern, skill, description in _extract_error_patterns(
                issue_text,
                fallback_skill=active_skill,
            ):
                await ErrorStore(self.db).record_error(
                    learner_id=learner_id,
                    skill=skill,
                    pattern=pattern,
                    description=description,
                    evidence_ref=f"session:{session_id}",
                    commit=False,
                )
                error_count += 1
                await MemoryWriter(self.db).record_event(
                    MemoryEventInput(
                        learner_id=learner_id,
                        event_type="chat_error_observed",
                        skill=skill,
                        source_type="session",
                        source_id=str(session_id),
                        session_id=session_id,
                        payload={
                            "pattern": pattern,
                            "description": description,
                            "issues": feedback.get("key_issues", []),
                        },
                        confidence=0.76,
                        created_by="system",
                    )
                )

        await MemoryWriter(self.db).record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type="chat_learning_turn",
                skill=active_skill,
                source_type="session",
                source_id=str(session_id),
                session_id=session_id,
                payload={
                    "summary": result.get("today_goal") or f"{active_skill} session",
                    "episode_type": result.get("session_type") or "daily_lesson",
                    "feedback_summary": feedback.get("summary"),
                },
                confidence=0.82,
                created_by="system",
            )
        )

        return MemoryExtractionResult(error_count=error_count)


def _normalize_skill(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _infer_skill(user_message: str, assistant_reply: str, skill_focus: str | None) -> str:
    explicit = _normalize_skill(skill_focus)
    if explicit:
        return explicit
    text = f"{user_message}\n{assistant_reply}".lower()
    for skill, keywords in _SKILL_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return skill
    return "general"


def _is_evaluable_submission(user_message: str, active_skill: str) -> bool:
    lower = user_message.lower()
    english_words = _WORD_RE.findall(user_message)
    return (
        active_skill in {"writing", "translation", "grammar", "reading"}
        and (
            len(english_words) >= 8
            or any(keyword in lower for keyword in ("批改", "作文", "翻译", "答案", "改错"))
        )
    )


def _extract_error_patterns(text: str, *, fallback_skill: str) -> list[tuple[str, str, str]]:
    lower = text.lower()
    found: list[tuple[str, str, str]] = []
    for pattern, default_skill, keywords, description in _ERROR_PATTERNS:
        if any(keyword.lower() in lower for keyword in keywords):
            skill = fallback_skill if fallback_skill != "general" else default_skill
            found.append((pattern, skill, description))
    return found[:3]


def _is_learning_activity(user_message: str, assistant_reply: str, active_skill: str) -> bool:
    if active_skill != "general":
        return True
    text = f"{user_message}\n{assistant_reply}".lower()
    return any(
        keyword in text
        for keyword in ("cet", "四级", "六级", "语法", "词汇", "阅读", "作文", "翻译", "复习")
    )


def _summarize_chat_learning(user_message: str, active_skill: str) -> str:
    normalized = " ".join(user_message.strip().split())
    if len(normalized) > 60:
        normalized = f"{normalized[:57]}..."
    if not normalized:
        normalized = "完成一次英语学习对话"
    return f"{active_skill}: {normalized}" if active_skill != "general" else normalized


def _source_ref(
    source_type: str,
    message_id: uuid.UUID | None,
    thread_id: uuid.UUID | None,
) -> str | None:
    if message_id:
        return f"{source_type}:{message_id}"
    if thread_id:
        return f"thread:{thread_id}"
    return None
