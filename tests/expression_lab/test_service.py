from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.expression_lab.schemas import AttemptRequest, CreateSessionRequest
from src.expression_lab.service import (
    _ensure_system_actions,
    ExpressionLabError,
    ExpressionLabService,
)
from src.models.expression_lab import (
    ExpressionLabAction,
    ExpressionLabAttempt,
    ExpressionLabEvent,
    ExpressionLabSession,
)
from src.models.knowledge import ExerciseAttempt
from src.models.learning_progress import LearningProgressItem
from src.models.memory import LearningMemoryEvent
from src.models.runtime import AgentEpisode, LearningEvent
from src.models.vocabulary import VocabularyItem
from src.models.writing_phrase import WritingPhrase


class _FakeScalars:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class _FakeResult:
    def __init__(
        self,
        value: Any = None,
        *,
        rows: list[Any] | None = None,
        joined_row: Any = None,
    ) -> None:
        self.value = value
        self.rows = rows or []
        self.joined_row = joined_row

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalar_one(self) -> Any:
        return self.value

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self.rows)

    def one_or_none(self) -> Any:
        return self.joined_row


def test_system_actions_always_offer_editable_one_to_three_practice() -> None:
    ui = _ensure_system_actions({"learning_actions": []})

    practice = next(
        action for action in ui["learning_actions"] if action["type"] == "create_practice"
    )
    assert practice["payload"]["count"] == 2
    assert practice["editable_fields"] == ["count", "focus"]
    assert practice["requires_confirmation"] is True
    assert {action["type"] for action in ui["learning_actions"]} >= {
        "create_practice",
        "dismiss_suggestion",
        "mark_completed",
    }


class _ServiceDb:
    def __init__(self, *results: _FakeResult) -> None:
        self.results = list(results)
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.statements: list[Any] = []
        self.flush_count = 0
        self.refreshed: list[Any] = []

    async def execute(self, statement: Any) -> _FakeResult:
        self.statements.append(statement)
        if not self.results:
            raise AssertionError(f"unexpected execute: {statement}")
        return self.results.pop(0)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)

    async def flush(self) -> None:
        self.flush_count += 1
        now = datetime.now(timezone.utc)
        for value in self.added:
            if hasattr(value, "id") and getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
                value.created_at = now
            if hasattr(value, "updated_at") and getattr(value, "updated_at", None) is None:
                value.updated_at = now

    async def refresh(self, value: Any) -> None:
        self.refreshed.append(value)


def _ready_session(
    *,
    learner_id: uuid.UUID | None = None,
    source_type: str = "manual",
    source_ref: str | None = None,
) -> ExpressionLabSession:
    session = ExpressionLabSession(
        learner_id=learner_id or uuid.uuid4(),
        episode_id=uuid.uuid4(),
        source_type=source_type,
        source_ref=source_ref,
        source_snapshot={},
        input_type="en_draft",
        input_text="I am agree with you.",
        context="daily_chat",
        style_goal="natural",
        current_level="B1",
        needs_practice=True,
        status="ready",
        ui_spec_json={
            "version": "expression_ui.v1",
            "blocks": [
                {
                    "id": "practice-1",
                    "type": "micro_practice",
                    "title": "马上练一次",
                    "data": {
                        "questions": [
                            {
                                "id": "question-1",
                                "type": "rewrite",
                                "prompt": "改写：I am agree with you.",
                                "skill": "grammar",
                            }
                        ]
                    },
                }
            ],
            "learning_actions": [],
        },
        grading_spec_json={
            "practice-1": {
                "question-1": {
                    "answer": "I agree with you",
                    "accepted_answers": ["I agree with you."],
                    "target_expression": "agree with",
                    "hint": "agree 前不使用 be",
                    "explanation": "agree 是实义动词。",
                    "skill": "grammar",
                }
            }
        },
        diagnostics_json={},
    )
    session.id = uuid.uuid4()
    session.created_at = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)
    return session


@pytest.mark.parametrize(
    ("input_type", "text"),
    [
        ("zh_intent", "这个观点太绝对了，怎样委婉表达？"),
        ("en_draft", "I am agree with you."),
        (
            "good_sentence",
            "What matters most is not speed, but consistency.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_create_session_preserves_three_core_inputs_and_starts_audited_episode(
    input_type: str,
    text: str,
) -> None:
    learner_id = uuid.uuid4()
    db = _ServiceDb()

    session = await ExpressionLabService(db).create_session(
        learner_id=learner_id,
        request=CreateSessionRequest(
            input_type=input_type,  # type: ignore[arg-type]
            text=text,
            context="group_chat",
            style="polite",
            current_level="B1",
            needs_practice=True,
        ),
    )

    assert session.learner_id == learner_id
    assert session.input_type == input_type
    assert session.input_text == text
    assert session.status == "generating"
    assert session.episode_id is not None
    episode = next(value for value in db.added if isinstance(value, AgentEpisode))
    assert episode.status == "running"
    assert episode.task_spec["target"]["target_type"] == "expression_lab_session"
    assert episode.task_spec["expected_output"] == {
        "schema": "expression_ui.v1",
        "practice": True,
    }
    assert any(
        isinstance(value, ExpressionLabEvent) and value.event_type == "session_created"
        for value in db.added
    )
    assert any(
        isinstance(value, LearningEvent)
        and value.event_type == "expression_lab_session_created"
        for value in db.added
    )


@pytest.mark.asyncio
async def test_group_signal_open_is_learner_scoped_and_does_not_accept_signal() -> None:
    learner_id = uuid.uuid4()
    signal_id = uuid.uuid4()
    signal = SimpleNamespace(
        id=signal_id,
        signal_type="expression_gap",
        target_type="writing_phrase",
        target_label="委婉表达不同意见",
        confidence=0.91,
        evidence_text="这个观点太绝对了",
        normalized_note="需要委婉表达",
        recommendation_reason="适合比较语气强度",
        status="candidate",
    )
    message = SimpleNamespace(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        occurred_at=datetime.now(timezone.utc),
    )
    source = SimpleNamespace(
        id=message.source_id,
        display_name="英语学习群",
        platform="feishu",
    )
    db = _ServiceDb(_FakeResult(joined_row=(signal, message, source)))

    session = await ExpressionLabService(db).create_session(
        learner_id=learner_id,
        request=CreateSessionRequest(
            input_type="zh_intent",
            text="这个观点太绝对了",
            source_signal_id=signal_id,
        ),
    )

    assert signal.status == "candidate"
    assert session.source_type == "group_learning_signal"
    assert session.source_ref == str(signal_id)
    assert session.source_snapshot["evidence_text"] == signal.evidence_text
    source_query = str(db.statements[0])
    assert "group_learning_signals.learner_id" in source_query
    assert "group_learning_signals.id" in source_query


@pytest.mark.asyncio
async def test_missing_or_foreign_source_signal_is_not_opened() -> None:
    db = _ServiceDb(_FakeResult(joined_row=None))

    with pytest.raises(ExpressionLabError) as error:
        await ExpressionLabService(db).create_session(
            learner_id=uuid.uuid4(),
            request=CreateSessionRequest(
                input_type="zh_intent",
                text="怎么表达？",
                source_signal_id=uuid.uuid4(),
            ),
        )

    assert error.value.code == "source_signal_not_found"
    assert error.value.status_code == 404
    assert db.added == []


@pytest.mark.asyncio
async def test_attempt_writes_expression_attempt_exercise_attempt_event_and_memory() -> None:
    session = _ready_session()
    db = _ServiceDb(_FakeResult(session), _FakeResult(0))

    result = await ExpressionLabService(db).submit_attempt(
        learner_id=session.learner_id,
        session_id=session.id,
        request=AttemptRequest(
            block_id="practice-1",
            question_id="question-1",
            answer="I agree with you.",
            response_time_ms=1250,
        ),
    )

    assert result.score == 100
    assert result.is_correct is True
    exercise_attempt = next(
        value for value in db.added if isinstance(value, ExerciseAttempt)
    )
    expression_attempt = next(
        value for value in db.added if isinstance(value, ExpressionLabAttempt)
    )
    event = next(value for value in db.added if isinstance(value, LearningEvent))
    memory = next(
        value for value in db.added if isinstance(value, LearningMemoryEvent)
    )
    assert expression_attempt.exercise_attempt_id == exercise_attempt.id
    assert exercise_attempt.learner_id == session.learner_id
    assert exercise_attempt.source_context["session_id"] == str(session.id)
    assert exercise_attempt.should_create_memory_evidence is True
    assert event.learner_id == session.learner_id
    assert event.event_type == "expression_lab_practice_submitted"
    assert memory.learner_id == session.learner_id
    assert memory.event_type == "expression_lab_practice_submitted"
    assert any(isinstance(value, ExpressionLabEvent) for value in db.added)


@pytest.mark.asyncio
async def test_materialized_action_never_expands_model_editable_fields() -> None:
    session = _ready_session()
    db = _ServiceDb(_FakeResult(rows=[]))
    service = ExpressionLabService(db)

    await service._materialize_actions(
        session,
        [
            {
                "id": "save-vocabulary-1",
                "type": "save_vocabulary",
                "label": "加入词汇本",
                "payload": {"word": "absolute", "meaning": "绝对的"},
                "editable_fields": ["meaning", "type", "unknown"],
                "requires_confirmation": False,
            }
        ],
    )

    action = next(value for value in db.added if isinstance(value, ExpressionLabAction))
    assert action.editable_fields == ["meaning"]
    assert action.requires_confirmation is True


@pytest.mark.asyncio
async def test_complete_is_idempotent_accepts_owned_signal_and_creates_no_asset() -> None:
    learner_id = uuid.uuid4()
    signal_id = uuid.uuid4()
    session = _ready_session(
        learner_id=learner_id,
        source_type="group_learning_signal",
        source_ref=str(signal_id),
    )
    signal = SimpleNamespace(
        id=signal_id,
        learner_id=learner_id,
        status="candidate",
        applied_target_type=None,
        applied_target_id=None,
        metadata_={},
    )
    episode = SimpleNamespace(
        id=session.episode_id,
        status="running",
        completed_at=None,
        verification_report=None,
        failure_type=None,
        error_message=None,
    )
    db = _ServiceDb(
        _FakeResult(session),
        _FakeResult(signal),
        _FakeResult(episode),
        _FakeResult(session),
    )
    service = ExpressionLabService(db)

    first = await service.complete_session(
        learner_id=learner_id,
        session_id=session.id,
    )
    event_count = len(db.added)
    second = await service.complete_session(
        learner_id=learner_id,
        session_id=session.id,
    )

    assert first is second is session
    assert db.refreshed == [session, session]
    assert session.status == "completed"
    assert session.completed_at is not None
    assert signal.status == "accepted"
    assert signal.applied_target_type == "expression_lab_session"
    assert signal.applied_target_id == session.id
    assert episode.status == "completed"
    assert len(db.added) == event_count
    assert any(
        isinstance(value, LearningMemoryEvent)
        and value.event_type == "expression_lab_session_completed"
        for value in db.added
    )
    assert not any(
        isinstance(value, (WritingPhrase, VocabularyItem, LearningProgressItem))
        for value in db.added
    )
    signal_query = str(db.statements[1])
    assert "group_learning_signals.learner_id" in signal_query


@pytest.mark.asyncio
async def test_delete_removes_session_trace_but_never_saved_assets() -> None:
    session = _ready_session()
    saved_phrase = WritingPhrase(
        learner_id=session.learner_id,
        text="I agree with you.",
        normalized_text="i agree with you.",
        examples=[],
        notes=[],
        mistakes=[],
        tags=[],
        source_type="expression_lab_session",
        source_ref=str(session.id),
        difficulty=2,
        is_favorite=True,
        is_archived=False,
        review_enabled=True,
        metadata_={"expression_lab_session_id": str(session.id)},
    )
    db = _ServiceDb(_FakeResult(session), _FakeResult())

    await ExpressionLabService(db).delete_session(
        learner_id=session.learner_id,
        session_id=session.id,
    )

    assert db.deleted == [session]
    assert saved_phrase not in db.deleted
    assert len(db.statements) == 2
    assert str(db.statements[1]).startswith("DELETE FROM agent_episodes")


@pytest.mark.asyncio
async def test_session_lookup_always_includes_learner_scope() -> None:
    db = _ServiceDb(_FakeResult(None))
    learner_id = uuid.uuid4()
    session_id = uuid.uuid4()

    with pytest.raises(ExpressionLabError) as error:
        await ExpressionLabService(db).get_session(
            learner_id=learner_id,
            session_id=session_id,
        )

    assert error.value.code == "session_not_found"
    statement = str(db.statements[0])
    assert "expression_lab_sessions.id" in statement
    assert "expression_lab_sessions.learner_id" in statement
