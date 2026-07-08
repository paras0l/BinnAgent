import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.group_learning.service import accept_signal, extract_signal_drafts, is_group_help_command
from src.models.group_learning import GroupLearningSignal
from src.models.learning_progress import LearningProgressItem
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
