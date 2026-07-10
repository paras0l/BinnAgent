import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.group_learning.service import (
    _record_expression_lab_reuses,
    accept_signal,
    expression_lab_phrase_matches_message,
    extract_signal_drafts,
    GroupLearningImportMessage,
    import_group_messages,
    is_group_help_command,
)
from src.models.expression_lab import ExpressionLabEvent, ExpressionLabSession
from src.models.group_learning import (
    GroupLearningMessage,
    GroupLearningSignal,
    GroupLearningSource,
)
from src.models.learning_progress import LearningProgressItem
from src.models.memory import LearningMemoryEvent
from src.models.vocabulary import VocabularyItem
from src.models.writing_phrase import WritingPhrase


def _none_result():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    return result


class FakeDb:
    def __init__(self):
        self.added = []
        self.execute = AsyncMock(return_value=_none_result())
        self.flush = AsyncMock(side_effect=self._flush)
        self.refresh = AsyncMock()

    def add(self, instance):
        self.added.append(instance)

    async def _flush(self):
        for instance in self.added:
            if getattr(instance, "id", None) is None:
                instance.id = uuid.uuid4()


def _signal(signal_type: str, target_label: str, metadata=None):
    signal = GroupLearningSignal(
        message_id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        signal_type=signal_type,
        target_type="grammar",
        target_label=target_label,
        confidence=0.93,
        evidence_text="I am agree with you.",
        normalized_note="agree 是动词，这里不需要 be。",
        recommendation_reason="写入语法推荐和学习画像弱点。",
        status="candidate",
        metadata_=metadata or {},
    )
    signal.id = uuid.uuid4()
    signal.created_at = datetime.now(timezone.utc)
    signal.updated_at = signal.created_at
    return signal


def test_extract_signal_drafts_covers_tags_grammar_expression_and_sentence():
    texts = [
        "#单词 nuance",
        "#语法 倒装句",
        "#收藏 What matters most is not how fast you learn, but how consistently you practice.",
        "#怎么说 这个观点太绝对了",
        "#纠错 I am agree with you.",
        "I have been learning English for two months.",
    ]

    signal_types = {
        draft.signal_type
        for text in texts
        for draft in extract_signal_drafts(text, source=SimpleNamespace(status="active"))
    }

    assert {
        "desired_vocabulary",
        "desired_grammar",
        "good_sentence",
        "expression_gap",
        "grammar_error",
        "grammar_correct_usage",
    }.issubset(signal_types)


def test_help_command_is_not_a_learning_signal():
    assert is_group_help_command("@_user_1 --help")
    assert extract_signal_drafts("@_user_1 --help", source=SimpleNamespace(status="active")) == []


def test_expression_lab_phrase_match_requires_exact_meaningful_phrase():
    assert expression_lab_phrase_matches_message(
        "That claim may be a little too strong.",
        "I agree with the first part. That claim may be a little too strong, though.",
    )
    assert expression_lab_phrase_matches_message("I disagree.", "I disagree!")
    assert not expression_lab_phrase_matches_message("I agree", "I agree with the plan")
    assert not expression_lab_phrase_matches_message(
        "That claim may be too strong.",
        "That claim is definitely too strong.",
    )


@pytest.mark.asyncio
async def test_later_group_message_records_expression_lab_reuse_without_raw_copy():
    learner_id = uuid.uuid4()
    session_id = uuid.uuid4()
    saved_at = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = GroupLearningSource(
        learner_id=learner_id,
        platform="feishu",
        source_type="group",
        display_name="学习群",
        external_group_key="chat-1",
    )
    source.id = uuid.uuid4()
    message = GroupLearningMessage(
        source_id=source.id,
        external_message_id="message-1",
        external_member_key="learner-member",
        learner_id=learner_id,
        message_type="text",
        content_text="That claim may be a little too strong, though.",
        content_hash="a" * 64,
        language_mix="en",
        occurred_at=saved_at + timedelta(hours=2),
        ingestion_status="pending_llm_analysis",
    )
    message.id = uuid.uuid4()
    phrase = WritingPhrase(
        learner_id=learner_id,
        text="That claim may be a little too strong.",
        normalized_text="that claim may be a little too strong.",
        tags=[],
        examples=[],
        notes=[],
        mistakes=[],
        source_type="expression_lab_session",
        source_ref=str(session_id),
        difficulty=2,
        is_favorite=True,
        is_archived=False,
        review_enabled=True,
        metadata_={
            "expression_lab_session_id": str(session_id),
            "expression_lab_action_id": str(uuid.uuid4()),
            "expression_lab_saved_at": saved_at.isoformat(),
        },
    )
    phrase.id = uuid.uuid4()
    phrase.created_at = saved_at
    phrase.updated_at = saved_at
    session = ExpressionLabSession(
        learner_id=learner_id,
        source_type="manual",
        input_type="zh_intent",
        input_text="这个观点太绝对了",
        status="completed",
    )
    session.id = session_id
    session.episode_id = None

    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = session
    event_result = MagicMock()
    event_result.scalars.return_value.all.return_value = []
    db = FakeDb()
    db.execute = AsyncMock(side_effect=[session_result, event_result])

    count = await _record_expression_lab_reuses(
        db,
        source=source,
        message=message,
        message_text=message.content_text or "",
        phrases=[phrase],
    )

    assert count == 1
    reuse_event = next(item for item in db.added if isinstance(item, ExpressionLabEvent))
    memory_event = next(item for item in db.added if isinstance(item, LearningMemoryEvent))
    assert reuse_event.event_type == "expression_reused"
    assert reuse_event.payload_json["group_learning_message_id"] == str(message.id)
    assert "content_text" not in reuse_event.payload_json
    assert memory_event.event_type == "expression_lab_expression_reused"
    assert memory_event.payload["confirmed_asset"] is True
    assert phrase.metadata_["expression_lab_reuse_count"] == 1
    assert phrase.metadata_["expression_lab_last_reused_at"] == message.occurred_at.isoformat()


@pytest.mark.asyncio
async def test_expression_lab_reuse_ignores_pre_save_message():
    learner_id = uuid.uuid4()
    session_id = uuid.uuid4()
    saved_at = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = SimpleNamespace(id=uuid.uuid4(), learner_id=learner_id)
    message = SimpleNamespace(
        id=uuid.uuid4(),
        external_message_id="message-2",
        content_hash="b" * 64,
        occurred_at=saved_at - timedelta(minutes=1),
    )
    phrase = SimpleNamespace(
        id=uuid.uuid4(),
        learner_id=learner_id,
        text="That claim may be a little too strong.",
        source_type="expression_lab_session",
        source_ref=str(session_id),
        created_at=saved_at,
        metadata_={
            "expression_lab_session_id": str(session_id),
            "expression_lab_saved_at": saved_at.isoformat(),
        },
    )
    db = FakeDb()

    count = await _record_expression_lab_reuses(
        db,
        source=source,
        message=message,
        message_text="That claim may be a little too strong.",
        phrases=[phrase],
    )

    assert count == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_expression_lab_reuse_is_idempotent_for_same_phrase_and_message():
    learner_id = uuid.uuid4()
    session_id = uuid.uuid4()
    phrase_id = uuid.uuid4()
    message_id = uuid.uuid4()
    saved_at = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    source = SimpleNamespace(id=uuid.uuid4(), learner_id=learner_id)
    message = SimpleNamespace(
        id=message_id,
        external_message_id="message-3",
        content_hash="c" * 64,
        occurred_at=saved_at + timedelta(minutes=1),
    )
    phrase = SimpleNamespace(
        id=phrase_id,
        learner_id=learner_id,
        text="That claim may be a little too strong.",
        source_type="expression_lab_session",
        source_ref=str(session_id),
        created_at=saved_at,
        metadata_={
            "expression_lab_session_id": str(session_id),
            "expression_lab_saved_at": saved_at.isoformat(),
        },
    )
    session = SimpleNamespace(id=session_id, episode_id=None)
    existing_event = SimpleNamespace(
        payload_json={
            "group_learning_message_id": str(message_id),
            "writing_phrase_id": str(phrase_id),
        }
    )
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = session
    event_result = MagicMock()
    event_result.scalars.return_value.all.return_value = [existing_event]
    db = FakeDb()
    db.execute = AsyncMock(side_effect=[session_result, event_result])

    count = await _record_expression_lab_reuses(
        db,
        source=source,
        message=message,
        message_text="That claim may be a little too strong.",
        phrases=[phrase],
    )

    assert count == 0
    assert db.added == []


@pytest.mark.asyncio
async def test_group_import_reports_expression_lab_reuse_count(monkeypatch):
    from src.group_learning import service as group_service

    learner_id = uuid.uuid4()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        learner_id=learner_id,
        status="active",
        allowed_senders=[],
        last_seen_at=None,
        last_import_summary={},
    )
    participant = SimpleNamespace(
        external_member_key="learner-member",
        display_name="Learner",
        learner_id=learner_id,
        role="learner",
        analysis_enabled=True,
        last_message_at=None,
    )
    monkeypatch.setattr(group_service, "_get_source", AsyncMock(return_value=source))
    monkeypatch.setattr(
        group_service,
        "_participants_by_member_key",
        AsyncMock(return_value={"learner-member": participant}),
    )
    monkeypatch.setattr(
        group_service,
        "_expression_lab_phrases_for_learner",
        AsyncMock(return_value=[SimpleNamespace(text="That claim may be too strong.")]),
    )
    monkeypatch.setattr(group_service, "_find_existing_message", AsyncMock(return_value=None))
    monkeypatch.setattr(
        group_service,
        "_record_expression_lab_reuses",
        AsyncMock(return_value=1),
    )
    occurred_at = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
    db = FakeDb()

    result = await import_group_messages(
        db,
        source_id=source.id,
        messages=[
            GroupLearningImportMessage(
                external_message_id="message-4",
                external_member_key="learner-member",
                content_text="That claim may be too strong.",
                occurred_at=occurred_at,
            )
        ],
    )

    assert result.imported_count == 1
    assert result.expression_reuse_count == 1
    assert source.last_import_summary["expression_reuse_count"] == 1
    assert source.last_seen_at == occurred_at


@pytest.mark.asyncio
async def test_accept_grammar_signal_writes_learning_progress():
    db = FakeDb()
    signal = _signal("grammar_error", "agree 不需要 be")

    updated = await accept_signal(db, signal)

    assert updated.status == "accepted"
    assert updated.applied_target_type == "learning_progress_item"
    assert isinstance(db.added[0], LearningProgressItem)
    assert db.added[0].skill == "grammar"
    assert db.added[0].metadata_["group_learning_signal_id"] == str(signal.id)


@pytest.mark.asyncio
async def test_accept_vocabulary_signal_writes_vocabulary_candidate():
    db = FakeDb()
    signal = _signal("desired_vocabulary", "nuance")

    updated = await accept_signal(db, signal)

    assert updated.status == "accepted"
    assert updated.applied_target_type == "vocabulary_item"
    assert any(isinstance(item, VocabularyItem) and item.canonical_key == "nuance" for item in db.added)


@pytest.mark.asyncio
async def test_accept_good_sentence_writes_phrase_candidate():
    db = FakeDb()
    signal = _signal(
        "good_sentence",
        "What matters most is not A, but B.",
        metadata={"sentence": "What matters most is not how fast you learn, but how consistently you practice."},
    )

    updated = await accept_signal(db, signal)

    assert updated.status == "accepted"
    assert updated.applied_target_type == "writing_phrase"
    assert any(isinstance(item, WritingPhrase) and item.review_enabled for item in db.added)
