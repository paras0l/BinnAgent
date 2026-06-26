import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.memory.curator import MemoryCurator
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryEventInput, MemoryOperationInput
from src.memory.writer import MemoryWriter
from src.models.error_pattern import ErrorPattern
from src.models.memory import LearnerMemorySettings, LearningMemoryEvent, MemoryOperation


def _result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_memory_writer_records_event_and_operation() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    learner_id = uuid.uuid4()

    event = await MemoryWriter(db).record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="vocabulary_attempted",
            skill="Word",
            source_type="vocabulary_attempt",
            source_id="attempt-1",
            payload={"result": "incorrect", "empty": None},
            confidence=1.5,
        )
    )
    operation = await MemoryWriter(db).record_operation(
        MemoryOperationInput(
            learner_id=learner_id,
            operation_type="delete",
            target_type="error_pattern",
            target_id="pattern-1",
        )
    )

    assert event.skill == "vocabulary"
    assert event.confidence == 1.0
    assert event.payload == {"result": "incorrect"}
    assert operation.operation_type == "delete"
    assert db.add.call_count == 2
    assert db.flush.await_count == 2


@pytest.mark.asyncio
async def test_curator_aggregates_events_into_error_pattern() -> None:
    learner_id = uuid.uuid4()
    event = LearningMemoryEvent(
        learner_id=learner_id,
        event_type="vocabulary_mistake_recorded",
        skill="vocabulary",
        source_type="vocabulary_attempt",
        source_id="attempt-1",
        payload={"result": "incorrect", "error_type": "spelling_error"},
        confidence=0.9,
        visibility="private",
        created_by="system",
        occurred_at=datetime.now(timezone.utc),
    )
    event.id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=[_result([event]), _one(None), _result([]), _one(None)])

    result = await MemoryCurator(db).curate_learner(learner_id)

    assert result["event_count"] == 1
    added_patterns = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], ErrorPattern)]
    assert added_patterns
    assert added_patterns[0].pattern == "spelling_error"


@pytest.mark.asyncio
async def test_retriever_excludes_deleted_memory_targets() -> None:
    learner_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    pattern = ErrorPattern(
        learner_id=learner_id,
        skill="writing",
        pattern="weak_transition",
        description="递进表达单一",
        frequency=3,
        confidence=0.8,
        status="active",
        evidence_refs=["essay_feedback:1"],
    )
    pattern.id = pattern_id
    operation = MemoryOperation(
        learner_id=learner_id,
        operation_type="delete",
        target_type="error_pattern",
        target_id=str(pattern_id),
    )
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result([operation]),
            _one(None),
            _result([pattern]),
            _result([]),
            _result([]),
            _result([]),
        ]
    )

    context = await MemoryRetriever(db).retrieve_context(
        learner_id=learner_id,
        reason="chat",
        skill="writing",
        log=False,
    )

    assert context.loaded_items == []
    assert f"error_pattern:{pattern_id}" in context.excluded_items


@pytest.mark.asyncio
async def test_retriever_excludes_low_confidence_by_default() -> None:
    learner_id = uuid.uuid4()
    pattern = ErrorPattern(
        learner_id=learner_id,
        skill="writing",
        pattern="maybe_transition",
        description="低置信递进表达推断",
        frequency=1,
        confidence=0.2,
        status="active",
        evidence_refs=[],
    )
    pattern.id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result([]),
            _one(None),
            _result([]),
            _result([]),
            _result([]),
        ]
    )

    context = await MemoryRetriever(db).retrieve_context(
        learner_id=learner_id,
        reason="chat",
        skill="writing",
        log=False,
    )

    assert context.loaded_items == []


@pytest.mark.asyncio
async def test_retriever_includes_low_confidence_when_user_enabled() -> None:
    learner_id = uuid.uuid4()
    pattern = ErrorPattern(
        learner_id=learner_id,
        skill="writing",
        pattern="maybe_transition",
        description="低置信递进表达推断",
        frequency=1,
        confidence=0.2,
        status="active",
        evidence_refs=[],
    )
    pattern.id = uuid.uuid4()
    settings = LearnerMemorySettings(
        learner_id=learner_id,
        low_confidence_memory_enabled=True,
    )
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result([]),
            _one(settings),
            _result([pattern]),
            _result([]),
            _result([]),
        ]
    )

    context = await MemoryRetriever(db).retrieve_context(
        learner_id=learner_id,
        reason="chat",
        skill="writing",
        log=False,
    )

    assert [item.payload["pattern"] for item in context.loaded_items] == ["maybe_transition"]
