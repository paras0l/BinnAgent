import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.api.vocabulary_learning import StartPracticeRequest, _first_text, _part_of_speech
from src.main import app
from src.models.vocabulary import VocabularyItem, VocabularyItemSource


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _rows(values):
    result = MagicMock()
    result.all.return_value = values
    return result


@pytest.fixture
def vocabulary_learning_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unit_summary_includes_full_textbook_total(client, vocabulary_learning_session):
    learner_id = uuid.uuid4()
    node_id = uuid.uuid4()
    item = VocabularyItem(
        learner_id=learner_id,
        word="morning",
        canonical_key="morning",
        entry_kind="word",
        status="learning",
        confidence=0.0,
        review_count=0,
    )
    item.id = uuid.uuid4()
    item.next_review_at = datetime.now(timezone.utc)
    source = VocabularyItemSource(
        learner_id=learner_id,
        vocabulary_item_id=item.id,
        source_type="textbook_unit",
        source_id=str(uuid.uuid4()),
        curriculum_node_id=node_id,
        display_label="七上 · SU1",
        active=True,
    )
    vocabulary_learning_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _scalar(7), _rows([(item, source)])]
    )

    response = await client.get(f"/api/learners/{learner_id}/vocabulary/units/{node_id}/summary")

    assert response.status_code == 200
    assert response.json() == {
        "unit_id": str(node_id),
        "total": 7,
        "enrolled": 1,
        "new": 7,
        "learning": 1,
        "mastered": 0,
        "due": 1,
    }


def test_structured_meaning_keeps_chinese_definition_and_part_of_speech() -> None:
    item = MagicMock()
    item.meanings = [{"part_of_speech": "n.", "definition_zh": "早晨；上午"}]
    item.entry_kind = "word"

    assert _first_text(item.meanings) == "早晨；上午"
    assert _part_of_speech(item) == "n."


def test_practice_limit_supports_source_bounded_custom_value() -> None:
    assert StartPracticeRequest(mode="spelling", limit=51).limit == 51
    with pytest.raises(ValueError):
        StartPracticeRequest(mode="spelling", limit=501)
