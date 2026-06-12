import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.vocabulary_store import VocabularyStore
from src.models.vocabulary import VocabularyItem


@pytest.fixture
def mock_db():
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def store(mock_db):
    return VocabularyStore(db=mock_db)


class TestAddWord:
    @pytest.mark.asyncio
    async def test_add_word_creates_new_item(self, store, mock_db):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        item = await store.add_word(
            learner_id=learner_id,
            word="hello",
            phonetic="/həˈloʊ/",
            level="A1",
            meanings=[{"pos": "interjection", "definition": "used as a greeting"}],
            collocations=["say hello", "hello world"],
            examples=["Hello, how are you?"],
            source_ref="CET-4 Word List",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        added_item = mock_db.add.call_args[0][0]
        assert isinstance(added_item, VocabularyItem)
        assert added_item.learner_id == learner_id
        assert added_item.word == "hello"
        assert added_item.phonetic == "/həˈloʊ/"
        assert added_item.level == "A1"
        assert added_item.status == "learning"
        assert added_item.confidence == 0.0
        assert added_item.review_count == 0
        assert added_item.next_review_at is not None

    @pytest.mark.asyncio
    async def test_add_duplicate_word_returns_existing(self, store, mock_db):
        learner_id = uuid.uuid4()
        existing_item = VocabularyItem(
            id=uuid.uuid4(),
            learner_id=learner_id,
            word="hello",
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_item
        mock_db.execute = AsyncMock(return_value=mock_result)

        item = await store.add_word(
            learner_id=learner_id,
            word="hello",
            phonetic="/həˈloʊ/",
            level="A1",
            meanings=[],
            collocations=[],
            examples=[],
            source_ref=None,
        )

        assert item is existing_item
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()


class TestGetWord:
    @pytest.mark.asyncio
    async def test_get_word_found(self, store, mock_db):
        learner_id = uuid.uuid4()
        expected = VocabularyItem(
            id=uuid.uuid4(),
            learner_id=learner_id,
            word="world",
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await store.get_word(learner_id, "world")

        assert result is expected
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_word_not_found(self, store, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await store.get_word(uuid.uuid4(), "nonexistent")

        assert result is None


class TestGetDueReviews:
    @pytest.mark.asyncio
    async def test_get_due_reviews_filters_by_date(self, store, mock_db):
        learner_id = uuid.uuid4()
        due_item = VocabularyItem(
            id=uuid.uuid4(),
            learner_id=learner_id,
            word="hello",
            next_review_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status="learning",
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [due_item]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        items = await store.get_due_reviews(learner_id, limit=20)

        assert len(items) == 1
        assert items[0].word == "hello"

    @pytest.mark.asyncio
    async def test_get_due_reviews_returns_empty_when_none_due(self, store, mock_db):
        learner_id = uuid.uuid4()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        items = await store.get_due_reviews(learner_id, limit=20)

        assert len(items) == 0


class TestUpdateConfidence:
    @pytest.mark.asyncio
    async def test_update_confidence_correct(self, store, mock_db):
        item_id = uuid.uuid4()
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.5,
            review_count=0,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=True, response_time_ms=1500)

        assert updated.confidence == 0.6
        assert updated.review_count == 1
        assert updated.status == "learning"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_confidence_wrong(self, store, mock_db):
        item_id = uuid.uuid4()
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.5,
            review_count=0,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=False, response_time_ms=1500)

        assert updated.confidence == 0.35
        assert updated.review_count == 1
        assert updated.status == "learning"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_confidence_reaches_mastered(self, store, mock_db):
        item_id = uuid.uuid4()
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.85,
            review_count=3,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=True, response_time_ms=2000)

        assert updated.confidence == 0.95
        assert updated.review_count == 4
        assert updated.status == "mastered"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_confidence_caps_at_one(self, store, mock_db):
        item_id = uuid.uuid4()
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.95,
            review_count=0,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=True, response_time_ms=1000)

        assert updated.confidence == 1.0
        assert updated.status == "mastered"

    @pytest.mark.asyncio
    async def test_update_confidence_floors_at_zero(self, store, mock_db):
        item_id = uuid.uuid4()
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.1,
            review_count=0,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=False, response_time_ms=500)

        assert updated.confidence == 0.0
        assert updated.review_count == 1

    @pytest.mark.asyncio
    async def test_update_confidence_raises_on_not_found(self, store, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="VocabularyItem with id"):
            await store.update_confidence(uuid.uuid4(), correct=True, response_time_ms=1000)

    @pytest.mark.asyncio
    async def test_update_confidence_correct_sets_sm2_interval(self, store, mock_db):
        item_id = uuid.uuid4()
        start_time = datetime.now(timezone.utc)
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.3,
            review_count=0,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=True, response_time_ms=1000)

        assert updated.review_count == 1
        expected = start_time + timedelta(days=1)
        assert updated.next_review_at is not None
        assert abs((updated.next_review_at - expected).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_update_confidence_correct_uses_increasing_intervals(self, store, mock_db):
        item_id = uuid.uuid4()
        start_time = datetime.now(timezone.utc)
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.5,
            review_count=5,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=True, response_time_ms=1000)

        assert updated.review_count == 6
        expected = start_time + timedelta(days=30)
        assert abs((updated.next_review_at - expected).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_update_confidence_wrong_sets_one_day_interval(self, store, mock_db):
        item_id = uuid.uuid4()
        start_time = datetime.now(timezone.utc)
        item = VocabularyItem(
            id=item_id,
            learner_id=uuid.uuid4(),
            word="hello",
            confidence=0.5,
            review_count=5,
            status="learning",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        updated = await store.update_confidence(item_id, correct=False, response_time_ms=1000)

        assert updated.review_count == 6
        expected = start_time + timedelta(days=1)
        assert abs((updated.next_review_at - expected).total_seconds()) < 5
