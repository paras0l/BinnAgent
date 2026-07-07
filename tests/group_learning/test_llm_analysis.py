import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.group_learning.llm_analysis import analyze_pending_group_learning_messages
from src.models.group_learning import GroupLearningMessage, GroupLearningSignal, GroupLearningSource


class _Result:
    def __init__(self, *, items=None, one=None):
        self._items = items or []
        self._one = one

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._one


class _FakeDb:
    def __init__(self, execute_results):
        self.execute = AsyncMock(side_effect=execute_results)
        self.flush = AsyncMock()
        self.added = []

    def add(self, item):
        self.added.append(item)


class _FakeExecutor:
    async def execute(self, **kwargs):
        messages = kwargs["variables"]["messages"]
        return SimpleNamespace(
            validated_output={
                "signals": [
                    {
                        "message_id": messages[0]["message_id"],
                        "signal_type": "desired_grammar",
                        "target_type": "grammar",
                        "target_label": "被动语态",
                        "confidence": 0.88,
                        "evidence_text": messages[0]["text"],
                        "normalized_note": "用户想学习被动语态。",
                        "recommendation_reason": "自然语言学习意图明确。",
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_analyze_pending_messages_batches_llm_signals_and_marks_done():
    learner_id = uuid.uuid4()
    source = GroupLearningSource(
        learner_id=learner_id,
        platform="feishu",
        display_name="英语学习群",
        external_group_key="oc_1",
    )
    source.id = uuid.uuid4()
    message = GroupLearningMessage(
        source_id=source.id,
        external_message_id="om_1",
        external_member_key="ou_1",
        learner_id=learner_id,
        message_type="text",
        content_text="我想要学习被动语句",
        content_hash="hash",
        language_mix="zh",
        occurred_at=datetime.now(timezone.utc),
        ingestion_status="pending_llm_analysis",
    )
    message.id = uuid.uuid4()
    db = _FakeDb([
        _Result(items=[message]),
        _Result(one=None),
        _Result(items=[]),
    ])

    result = await analyze_pending_group_learning_messages(
        db,
        source=source,
        limit=10,
        executor=_FakeExecutor(),
    )

    assert result.analyzed_message_count == 1
    assert result.generated_signal_count == 1
    assert result.remaining_pending_count == 0
    assert message.ingestion_status == "llm_analyzed"
    assert any(
        isinstance(item, GroupLearningSignal) and item.target_label == "被动语态"
        for item in db.added
    )
