import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.api import vocabulary_learning as vocabulary_learning_api
from src.api.vocabulary_learning import (
    StartPracticeRequest,
    start_practice_session,
    _first_text,
    _part_of_speech,
)
from src.main import app
from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.vocabulary import (
    VocabularyItem,
    VocabularyItemSource,
    VocabularyPracticeSession,
    VocabularyUserOverride,
)
from src.vocabulary.learning import EnrollmentResult


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


def _items(values):
    scalar_result = MagicMock()
    scalar_result.all.return_value = values
    scalar_result.unique.return_value.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalar_result
    return result


def _unit_word_points(source_id: uuid.UUID, node_id: uuid.UUID, count: int) -> list[KnowledgePoint]:
    points = []
    for index in range(count):
        point = KnowledgePoint(
            source_id=source_id,
            curriculum_node_id=node_id,
            canonical_key=f"vocabulary.word-{index}",
            type="vocabulary",
            title=f"word{index}",
            summary=f"Unit vocabulary {index}",
            status="published",
            content={"role": "unit_wordlist", "unit_order": index + 1},
        )
        point.id = uuid.uuid4()
        points.append(point)
    return points


@pytest.fixture
def vocabulary_learning_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unit_summary_includes_full_textbook_total(client, vocabulary_learning_session):
    learner_id = uuid.uuid4()
    knowledge_source = KnowledgeSource(
        title="英语 七年级上册",
        filename="textbook.pdf",
        status="published",
        visibility="public",
        sha256="a" * 64,
        file_size=1,
    )
    knowledge_source.id = uuid.uuid4()
    node_id = uuid.uuid4()
    node = CurriculumNode(
        source_id=knowledge_source.id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
    )
    node.id = node_id
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
    item_source = VocabularyItemSource(
        learner_id=learner_id,
        vocabulary_item_id=item.id,
        source_type="textbook_unit",
        source_id=str(uuid.uuid4()),
        curriculum_node_id=node_id,
        display_label="七上 · SU1",
        active=True,
    )
    unit_points = _unit_word_points(knowledge_source.id, node_id, 7)
    vocabulary_learning_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(node),
            _scalar(knowledge_source),
            _items(unit_points),
            _rows([(item, item_source)]),
        ]
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


@pytest.mark.asyncio
async def test_unit_new_session_falls_back_to_learning_words(monkeypatch) -> None:
    learner_id = uuid.uuid4()
    node_id = uuid.uuid4()
    node = CurriculumNode(
        source_id=uuid.uuid4(),
        node_type="unit",
        title="Starter Unit 1",
        ordinal=1,
    )
    node.id = node_id
    item = VocabularyItem(
        learner_id=learner_id,
        word="good",
        canonical_key="good",
        entry_kind="word",
        status="learning",
        confidence=0.18,
        review_count=1,
        next_review_at=datetime.now(timezone.utc),
    )
    item.id = uuid.uuid4()
    db = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def flush() -> None:
        for value in added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    db.flush = AsyncMock(side_effect=flush)
    db.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(node),
            _items([]),
            _items([item]),
        ]
    )
    monkeypatch.setattr(vocabulary_learning_api, "excluded_item_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        vocabulary_learning_api,
        "enroll_unit_vocabulary",
        AsyncMock(return_value=EnrollmentResult(total=1, newly_added=0, source_linked=0, already_known=1)),
    )

    result = await start_practice_session(
        learner_id,
        StartPracticeRequest(mode="new", prompt_mode="meaning", curriculum_node_id=node_id),
        db,
    )

    assert result.total == 1
    assert result.mode == "new"


@pytest.mark.asyncio
async def test_too_easy_marks_current_word_mastered_and_advances(
    client, vocabulary_learning_session
):
    learner_id = uuid.uuid4()
    item = VocabularyItem(
        learner_id=learner_id,
        word="hello",
        canonical_key="hello",
        entry_kind="word",
        status="learning",
        confidence=0.2,
        review_count=0,
        next_review_at=datetime.now(timezone.utc),
    )
    item.id = uuid.uuid4()
    practice = VocabularyPracticeSession(
        learner_id=learner_id,
        mode="new",
        prompt_mode="context",
        accent="uk",
        status="in_progress",
        item_ids=[str(item.id)],
        current_index=0,
        correct_count=0,
        hinted_count=0,
        revealed_count=0,
        started_at=datetime.now(timezone.utc),
    )
    practice.id = uuid.uuid4()
    added: list[object] = []
    vocabulary_learning_session.add = MagicMock(side_effect=added.append)
    vocabulary_learning_session.flush = AsyncMock()
    vocabulary_learning_session.execute = AsyncMock(
        side_effect=[_one(practice), _one(item), _one(None)]
    )

    response = await client.post(
        f"/api/learners/{learner_id}/vocabulary/sessions/{practice.id}/too-easy",
        json={"vocabulary_item_id": str(item.id)},
    )

    assert response.status_code == 200
    assert response.json()["completed"] == 1
    assert response.json()["review_preference"] == "too_easy"
    assert practice.status == "completed"
    assert item.status == "mastered"
    assert item.confidence == pytest.approx(0.9)
    override = next(value for value in added if isinstance(value, VocabularyUserOverride))
    assert override.review_preference == "too_easy"
