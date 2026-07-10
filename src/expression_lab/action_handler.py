from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.expression_lab.schemas import (
    ActionRequest,
    CopyExpressionPayload,
    CreatePracticePayload,
    DismissSuggestionPayload,
    MarkCompletedPayload,
    SaveGrammarPointPayload,
    SaveVocabularyPayload,
    SaveWritingPhrasePayload,
)
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.expression_lab import (
    ExpressionLabAction,
    ExpressionLabEvent,
    ExpressionLabSession,
)
from src.models.learning_progress import LearningProgressItem
from src.models.vocabulary import VocabularyItem, VocabularyItemSource
from src.models.writing_phrase import WritingPhrase
from src.runtime.episode import EpisodeRuntime
from src.vocabulary.learning import canonical_vocabulary_key


ActionCallback = Callable[
    [ExpressionLabSession, ExpressionLabAction, dict[str, Any]],
    Awaitable[tuple[str | None, str | None, dict[str, Any]]],
]


@dataclass(frozen=True)
class ActionExecutionResult:
    action_id: uuid.UUID
    status: str
    applied_target_type: str | None
    applied_target_id: str | None
    payload: dict[str, Any]


class ExpressionLabActionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExpressionLabActionHandler:
    def __init__(
        self,
        db: AsyncSession,
        *,
        create_practice: ActionCallback | None = None,
        mark_completed: ActionCallback | None = None,
    ) -> None:
        self.db = db
        self.create_practice = create_practice
        self.mark_completed = mark_completed

    async def execute(
        self,
        *,
        session: ExpressionLabSession,
        action_id: uuid.UUID,
        request: ActionRequest,
    ) -> ActionExecutionResult:
        result = await self.db.execute(
            select(ExpressionLabAction)
            .where(
                ExpressionLabAction.id == action_id,
                ExpressionLabAction.session_id == session.id,
            )
            .with_for_update()
        )
        action = result.scalar_one_or_none()
        if action is None:
            raise ExpressionLabActionError("action_not_found", "Action not found")
        if action.status in {"applied", "dismissed"}:
            return _result(action)
        if session.status == "completed":
            raise ExpressionLabActionError(
                "session_completed", "Completed sessions cannot execute new actions"
            )
        if (
            action.requires_confirmation
            or action.action_type
            in {"save_writing_phrase", "save_vocabulary", "save_grammar_point"}
        ) and not request.confirmed:
            raise ExpressionLabActionError(
                "confirmation_required", "This action requires explicit confirmation"
            )
        if action.status == "applying":
            raise ExpressionLabActionError("action_in_progress", "Action is already in progress")

        payload = self._validated_payload(action, request.edits)
        action.status = "applying"
        action.confirmed_by_user = bool(request.confirmed)
        await self.db.flush()

        try:
            async with _optional_savepoint(self.db):
                target_type: str | None = None
                target_id: str | None = None
                response_payload: dict[str, Any] = {}
                if action.action_type == "save_writing_phrase":
                    target = await self._save_writing_phrase(session, action, payload)
                    target_type, target_id = "writing_phrase", str(target.id)
                elif action.action_type == "save_vocabulary":
                    target = await self._save_vocabulary(session, action, payload)
                    target_type, target_id = "vocabulary_item", str(target.id)
                elif action.action_type == "save_grammar_point":
                    target = await self._save_grammar_point(session, action, payload)
                    target_type, target_id = "learning_progress_item", str(target.id)
                elif action.action_type == "create_practice":
                    if self.create_practice is None:
                        raise ExpressionLabActionError(
                            "practice_callback_missing", "Practice creation is unavailable"
                        )
                    target_type, target_id, response_payload = await self.create_practice(
                        session, action, payload
                    )
                elif action.action_type == "copy_expression":
                    response_payload = {"text": payload["text"]}
                elif action.action_type == "dismiss_suggestion":
                    action.status = "dismissed"
                    response_payload = {"dismissed": True}
                elif action.action_type == "mark_completed":
                    if self.mark_completed is None:
                        raise ExpressionLabActionError(
                            "completion_callback_missing", "Completion is unavailable"
                        )
                    target_type, target_id, response_payload = await self.mark_completed(
                        session, action, payload
                    )
                else:
                    raise ExpressionLabActionError("unsupported_action", "Unsupported action")
        except Exception as exc:
            action.status = "failed"
            action.failure_code = (
                exc.code if isinstance(exc, ExpressionLabActionError) else "action_apply_failed"
            )
            action.failure_summary = "动作未执行，未写入任何学习资产。"
            await self._record_failure_event(session, action)
            await self.db.flush()
            return _result(action, {"error_code": action.failure_code})

        now = datetime.now(timezone.utc)
        if action.status != "dismissed":
            action.status = "applied"
        action.payload_json = payload
        action.applied_target_type = target_type
        action.applied_target_id = target_id
        action.applied_at = now
        action.failure_code = None
        action.failure_summary = None
        await self._record_action_event(session, action, response_payload)
        await self.db.flush()
        return _result(action, response_payload)

    def _validated_payload(
        self, action: ExpressionLabAction, edits: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(edits, dict):
            raise ExpressionLabActionError("invalid_edits", "Action edits must be an object")
        allowed = set(action.editable_fields or [])
        unexpected = set(edits) - allowed
        if unexpected:
            raise ExpressionLabActionError(
                "uneditable_fields", f"Fields cannot be edited: {', '.join(sorted(unexpected))}"
            )
        candidate = {**(action.payload_json or {}), **edits}
        model_type = _PAYLOAD_MODELS.get(action.action_type)
        if model_type is None:
            raise ExpressionLabActionError("unsupported_action", "Unsupported action")
        try:
            validated = model_type.model_validate(candidate)
        except ValidationError as exc:
            raise ExpressionLabActionError("invalid_action_payload", "Invalid action payload") from exc
        return validated.model_dump(mode="json", by_alias=True)

    async def _save_writing_phrase(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        payload: dict[str, Any],
    ) -> WritingPhrase:
        text = str(payload["text"]).strip()
        normalized = re.sub(r"\s+", " ", text).casefold()
        result = await self.db.execute(
            select(WritingPhrase).where(
                WritingPhrase.learner_id == session.learner_id,
                WritingPhrase.normalized_text == normalized,
            )
        )
        phrase = result.scalar_one_or_none()
        source = {
            "expression_lab_session_id": str(session.id),
            "expression_lab_action_id": str(action.id),
            "block_id": action.block_id,
            "template": payload.get("template"),
            # Group-learning imports use this timestamp to distinguish a genuine
            # later reuse from an older message that happened to be synced after
            # the phrase was saved.
            "expression_lab_saved_at": datetime.now(timezone.utc).isoformat(),
        }
        if phrase is None:
            phrase = WritingPhrase(
                learner_id=session.learner_id,
                text=text,
                normalized_text=normalized,
                chinese_meaning=payload.get("chinese_meaning") or None,
                explanation=payload.get("explanation") or None,
                usage_scene=payload.get("usage_scene") or session.context,
                usage_position="body",
                tags=list(payload.get("tags") or []),
                examples=[
                    {"sentence": example, "translation": ""}
                    for example in payload.get("examples") or []
                ],
                notes=[],
                mistakes=[],
                source_type="expression_lab_session",
                source_ref=str(session.id),
                source_raw_text=session.input_text,
                register_level=payload.get("register"),
                difficulty=2,
                is_favorite=True,
                is_archived=False,
                review_enabled=True,
                metadata_=source,
            )
            self.db.add(phrase)
            await self.db.flush()
        else:
            phrase.metadata_ = {**(phrase.metadata_ or {}), **source}
            phrase.is_favorite = True
        await self._memory_asset_saved(session, action, "writing_phrase", str(phrase.id), text)
        return phrase

    async def _save_vocabulary(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        payload: dict[str, Any],
    ) -> VocabularyItem:
        word = str(payload["word"]).strip()
        canonical = canonical_vocabulary_key(word)
        result = await self.db.execute(
            select(VocabularyItem).where(
                VocabularyItem.learner_id == session.learner_id,
                VocabularyItem.canonical_key == canonical,
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            meaning = str(payload.get("meaning") or "")
            item = VocabularyItem(
                learner_id=session.learner_id,
                word=word,
                canonical_key=canonical,
                entry_kind="phrase" if " " in canonical else "word",
                preferred_accent="auto",
                level="custom",
                meanings=[{"definition_zh": meaning}] if meaning else [],
                dictionary_senses=[],
                word_forms={},
                dictionary_tags=["expression_lab"],
                collocations=list(payload.get("collocations") or []),
                examples=list(payload.get("examples") or []),
                source_ref=f"expression_lab_session:{session.id}",
                status="learning",
                confidence=0.8,
                review_count=0,
                next_review_at=datetime.now(timezone.utc),
            )
            self.db.add(item)
            await self.db.flush()
        source_result = await self.db.execute(
            select(VocabularyItemSource).where(
                VocabularyItemSource.learner_id == session.learner_id,
                VocabularyItemSource.vocabulary_item_id == item.id,
                VocabularyItemSource.source_type == "expression_lab_session",
                VocabularyItemSource.source_id == str(session.id),
            )
        )
        source = source_result.scalar_one_or_none()
        if source is None:
            self.db.add(
                VocabularyItemSource(
                    learner_id=session.learner_id,
                    vocabulary_item_id=item.id,
                    source_type="expression_lab_session",
                    source_id=str(session.id),
                    reason=str(payload.get("reason") or "expression_lab")[:80],
                    priority=0.8,
                    display_label="Expression Lab",
                    context_snapshot={
                        "action_id": str(action.id),
                        "source_expression": payload.get("source_expression"),
                        "input_text": session.input_text,
                    },
                    active=True,
                )
            )
        await self._memory_asset_saved(session, action, "vocabulary", str(item.id), word)
        return item

    async def _save_grammar_point(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        payload: dict[str, Any],
    ) -> LearningProgressItem:
        topic = str(payload["topic"]).strip()
        item_id = re.sub(r"[^a-z0-9_-]+", "-", topic.casefold()).strip("-")[:150]
        if not item_id:
            digest = hashlib.sha256(topic.casefold().encode("utf-8")).hexdigest()[:20]
            item_id = f"expression-lab-{digest}"
        result = await self.db.execute(
            select(LearningProgressItem).where(
                LearningProgressItem.learner_id == session.learner_id,
                LearningProgressItem.skill == "grammar",
                LearningProgressItem.item_id == item_id,
            )
        )
        item = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        source = {
            "expression_lab_session_id": str(session.id),
            "expression_lab_action_id": str(action.id),
            "rule": payload.get("rule"),
            "error": payload.get("error"),
            "correction": payload.get("correction"),
            "minimal_pairs": payload.get("minimal_pairs") or [],
        }
        if item is None:
            item = LearningProgressItem(
                learner_id=session.learner_id,
                skill="grammar",
                item_id=item_id,
                title=topic,
                status="opened",
                is_favorite=True,
                opened_count=1,
                last_opened_at=now,
                metadata_=source,
            )
            self.db.add(item)
            await self.db.flush()
        else:
            item.opened_count = (item.opened_count or 0) + 1
            item.last_opened_at = now
            item.is_favorite = True
            item.metadata_ = {**(item.metadata_ or {}), **source}
        await self._memory_asset_saved(session, action, "grammar", str(item.id), topic)
        return item

    async def _memory_asset_saved(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        skill: str,
        target_id: str,
        label: str,
    ) -> None:
        await MemoryWriter(self.db).record_event(
            MemoryEventInput(
                learner_id=session.learner_id,
                event_type="expression_lab_asset_saved",
                skill=skill,
                source_type="expression_lab_session",
                source_id=str(session.id),
                payload={
                    "action_id": str(action.id),
                    "action_type": action.action_type,
                    "target_id": target_id,
                    "label": label,
                    "confirmed_by_user": True,
                },
                confidence=1.0,
                created_by="user",
            )
        )

    async def _record_action_event(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        response_payload: dict[str, Any],
    ) -> None:
        if action.action_type == "mark_completed":
            return
        event_type = {
            "copy_expression": "expression_copied",
            "dismiss_suggestion": "suggestion_dismissed",
            "mark_completed": "session_completed",
        }.get(action.action_type, "asset_saved")
        now = datetime.now(timezone.utc)
        payload = {
            "action_id": str(action.id),
            "spec_action_id": action.spec_action_id,
            "action_type": action.action_type,
            "block_id": action.block_id,
            "applied_target_type": action.applied_target_type,
            "applied_target_id": action.applied_target_id,
            **response_payload,
        }
        self.db.add(
            ExpressionLabEvent(
                session_id=session.id,
                event_type=event_type,
                payload_json=payload,
                occurred_at=now,
            )
        )
        if session.episode_id is not None:
            await EpisodeRuntime(self.db).append_event(
                episode_id=session.episode_id,
                learner_id=session.learner_id,
                event_type=f"expression_lab_{event_type}",
                source_module="expression_lab",
                target_type="expression_lab_action",
                target_id=str(action.id),
                payload=payload,
            )

    async def _record_failure_event(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
    ) -> None:
        payload = {
            "action_id": str(action.id),
            "spec_action_id": action.spec_action_id,
            "action_type": action.action_type,
            "error_code": action.failure_code,
        }
        now = datetime.now(timezone.utc)
        self.db.add(
            ExpressionLabEvent(
                session_id=session.id,
                event_type="action_failed",
                payload_json=payload,
                occurred_at=now,
            )
        )
        if session.episode_id is not None:
            await EpisodeRuntime(self.db).append_event(
                episode_id=session.episode_id,
                learner_id=session.learner_id,
                event_type="expression_lab_action_failed",
                source_module="expression_lab",
                target_type="expression_lab_action",
                target_id=str(action.id),
                payload=payload,
            )


_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "save_writing_phrase": SaveWritingPhrasePayload,
    "save_vocabulary": SaveVocabularyPayload,
    "save_grammar_point": SaveGrammarPointPayload,
    "create_practice": CreatePracticePayload,
    "copy_expression": CopyExpressionPayload,
    "dismiss_suggestion": DismissSuggestionPayload,
    "mark_completed": MarkCompletedPayload,
}
_PAYLOAD_EDIT_FIELDS: dict[str, frozenset[str]] = {
    "save_writing_phrase": frozenset(
        {
            "text",
            "chinese_meaning",
            "explanation",
            "usage_scene",
            "register",
            "template",
            "examples",
            "tags",
        }
    ),
    "save_vocabulary": frozenset(
        {"word", "meaning", "collocations", "examples", "source_expression", "reason"}
    ),
    "save_grammar_point": frozenset(
        {"topic", "rule", "error", "correction", "minimal_pairs"}
    ),
    "create_practice": frozenset({"count", "focus"}),
}


def editable_fields_for_action(action_type: str) -> list[str]:
    return sorted(_PAYLOAD_EDIT_FIELDS.get(action_type, frozenset()))


def _result(
    action: ExpressionLabAction, payload: dict[str, Any] | None = None
) -> ActionExecutionResult:
    return ActionExecutionResult(
        action_id=action.id,
        status=action.status,
        applied_target_type=action.applied_target_type,
        applied_target_id=action.applied_target_id,
        payload=payload or {},
    )


@asynccontextmanager
async def _optional_savepoint(db: AsyncSession):
    begin_nested = getattr(db, "begin_nested", None)
    if callable(begin_nested):
        async with begin_nested():
            yield
        return
    yield
