from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from src.expression_lab.action_handler import (
    ExpressionLabActionError,
    ExpressionLabActionHandler,
    editable_fields_for_action,
)
from src.expression_lab.schemas import ActionRequest
from src.models.expression_lab import ExpressionLabAction, ExpressionLabSession


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value


class _NestedTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: Any) -> None:
        return None


class _ActionDb:
    def __init__(self, action: ExpressionLabAction) -> None:
        self.action = action
        self.added: list[Any] = []
        self.flush_count = 0
        self.execute_count = 0

    async def execute(self, _statement: Any) -> _ScalarResult:
        self.execute_count += 1
        return _ScalarResult(self.action)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    def begin_nested(self) -> _NestedTransaction:
        return _NestedTransaction()


def _session() -> ExpressionLabSession:
    value = ExpressionLabSession(
        learner_id=uuid.uuid4(),
        source_type="manual",
        source_snapshot={},
        input_type="zh_intent",
        input_text="这个观点太绝对了",
        context="group_chat",
        needs_practice=True,
    )
    value.id = uuid.uuid4()
    return value


def _action(
    session: ExpressionLabSession,
    *,
    action_type: str = "save_vocabulary",
    payload: dict[str, Any] | None = None,
    editable_fields: list[str] | None = None,
    requires_confirmation: bool = True,
    status: str = "pending",
) -> ExpressionLabAction:
    defaults = {
        "save_writing_phrase": {"text": "That claim may be too absolute."},
        "save_vocabulary": {"word": "absolute", "meaning": "绝对的"},
        "save_grammar_point": {"topic": "agree 的用法", "rule": "agree 前不加 be"},
    }
    value = ExpressionLabAction(
        session_id=session.id,
        spec_action_id=f"spec-{action_type}",
        action_type=action_type,
        label="保存",
        payload_json=payload if payload is not None else defaults[action_type],
        editable_fields=editable_fields or [],
        requires_confirmation=requires_confirmation,
        status=status,
        confirmed_by_user=False,
    )
    value.id = uuid.uuid4()
    return value


@pytest.mark.parametrize(
    "action_type",
    ["save_writing_phrase", "save_vocabulary", "save_grammar_point"],
)
@pytest.mark.asyncio
async def test_every_save_action_requires_confirmation_even_for_legacy_dirty_record(
    action_type: str,
) -> None:
    session = _session()
    action = _action(
        session,
        action_type=action_type,
        requires_confirmation=False,
    )
    handler = ExpressionLabActionHandler(_ActionDb(action))  # type: ignore[arg-type]

    with pytest.raises(ExpressionLabActionError) as error:
        await handler.execute(
            session=session,
            action_id=action.id,
            request=ActionRequest(confirmed=False),
        )

    assert error.value.code == "confirmation_required"
    assert action.status == "pending"


def test_empty_editable_fields_means_no_client_edits() -> None:
    session = _session()
    action = _action(session, editable_fields=[])
    handler = ExpressionLabActionHandler(_ActionDb(action))  # type: ignore[arg-type]

    with pytest.raises(ExpressionLabActionError) as error:
        handler._validated_payload(action, {"meaning": "武断的"})

    assert error.value.code == "uneditable_fields"


def test_create_practice_allows_only_count_and_focus_edits() -> None:
    assert editable_fields_for_action("create_practice") == ["count", "focus"]


def test_only_fields_named_by_the_server_can_be_edited() -> None:
    session = _session()
    action = _action(session, editable_fields=["meaning"])
    handler = ExpressionLabActionHandler(_ActionDb(action))  # type: ignore[arg-type]

    payload = handler._validated_payload(action, {"meaning": "武断的；绝对的"})

    assert payload["word"] == "absolute"
    assert payload["meaning"] == "武断的；绝对的"
    with pytest.raises(ExpressionLabActionError) as error:
        handler._validated_payload(action, {"word": "categorical"})
    assert error.value.code == "uneditable_fields"


def test_edited_payload_is_revalidated_for_type_and_length() -> None:
    session = _session()
    action = _action(session, editable_fields=["word"])
    handler = ExpressionLabActionHandler(_ActionDb(action))  # type: ignore[arg-type]

    with pytest.raises(ExpressionLabActionError) as error:
        handler._validated_payload(action, {"word": ""})

    assert error.value.code == "invalid_action_payload"


@pytest.mark.asyncio
async def test_applied_action_is_idempotent_and_does_not_repeat_side_effects() -> None:
    session = _session()
    action = _action(session, status="applied")
    action.confirmed_by_user = True
    action.applied_target_type = "vocabulary_item"
    action.applied_target_id = "asset-1"
    db = _ActionDb(action)
    handler = ExpressionLabActionHandler(db)  # type: ignore[arg-type]

    async def unexpected_save(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("an applied action must not execute its side effect again")

    handler._save_vocabulary = unexpected_save  # type: ignore[method-assign]

    first = await handler.execute(
        session=session,
        action_id=action.id,
        request=ActionRequest(confirmed=True),
    )
    second = await handler.execute(
        session=session,
        action_id=action.id,
        request=ActionRequest(confirmed=True),
    )

    assert first == second
    assert first.applied_target_type == "vocabulary_item"
    assert first.applied_target_id == "asset-1"
    assert db.execute_count == 2
    assert db.flush_count == 0
    assert db.added == []


@pytest.mark.asyncio
async def test_confirmed_save_records_target_once() -> None:
    session = _session()
    action = _action(session, editable_fields=["meaning"])
    db = _ActionDb(action)
    handler = ExpressionLabActionHandler(db)  # type: ignore[arg-type]
    saved_id = uuid.uuid4()
    save_count = 0

    async def save_once(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal save_count
        save_count += 1
        return SimpleNamespace(id=saved_id)

    handler._save_vocabulary = save_once  # type: ignore[method-assign]

    result = await handler.execute(
        session=session,
        action_id=action.id,
        request=ActionRequest(confirmed=True, edits={"meaning": "武断的；绝对的"}),
    )
    replay = await handler.execute(
        session=session,
        action_id=action.id,
        request=ActionRequest(confirmed=True, edits={"meaning": "不会再次应用"}),
    )

    assert save_count == 1
    assert result.status == "applied"
    assert replay.applied_target_id == str(saved_id)
    assert action.payload_json["meaning"] == "武断的；绝对的"
    assert action.confirmed_by_user is True
