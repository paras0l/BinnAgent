import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import deps
from src.main import app


@pytest.fixture
def mock_session():
    """Override get_db_session with a controlled mock session."""
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


class TestAddWord:
    @pytest.mark.asyncio
    async def test_add_word(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.0
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_word = AsyncMock(return_value=mock_item)

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/add",
                json={"word": "hello", "phonetic": "/həˈloʊ/"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(word_id)
        assert data["word"] == "hello"
        assert data["phonetic"] == "/həˈloʊ/"
        assert data["status"] == "learning"
        assert data["confidence"] == 0.0
        assert data["next_review_at"] is None

    @pytest.mark.asyncio
    async def test_add_word_no_phonetic(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "world"
        mock_item.phonetic = None
        mock_item.status = "learning"
        mock_item.confidence = 0.0
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_word = AsyncMock(return_value=mock_item)

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/add",
                json={"word": "world"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(word_id)
        assert data["word"] == "world"
        assert data["phonetic"] is None

    @pytest.mark.asyncio
    async def test_add_word_calls_store_with_correct_args(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.5
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_word = AsyncMock(return_value=mock_item)

            await client.post(
                f"/api/learners/{learner_id}/vocabulary/add",
                json={
                    "word": "hello",
                    "phonetic": "/həˈloʊ/",
                    "level": "A1",
                    "meanings": ["a greeting"],
                },
            )

        mock_store.add_word.assert_awaited_once_with(
            learner_id=learner_id,
            word="hello",
            phonetic="/həˈloʊ/",
            level="A1",
            meanings=["a greeting"],
        )


class TestGetDueReviews:
    @pytest.mark.asyncio
    async def test_get_due_reviews(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.5
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.get_due_reviews = AsyncMock(return_value=[mock_item])

            response = await client.get(f"/api/learners/{learner_id}/vocabulary/due")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(word_id)
        assert data[0]["word"] == "hello"
        assert data[0]["phonetic"] == "/həˈloʊ/"
        assert data[0]["status"] == "learning"
        assert data[0]["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_get_due_reviews_empty(self, client, mock_session):
        learner_id = uuid.uuid4()

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.get_due_reviews = AsyncMock(return_value=[])

            response = await client.get(f"/api/learners/{learner_id}/vocabulary/due")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestReviewWord:
    @pytest.mark.asyncio
    async def test_review_word_correct(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.5
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.update_confidence = AsyncMock(return_value=mock_item)

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/review",
                json={"word_id": str(word_id), "correct": True, "response_time_ms": 1500},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(word_id)
        assert data["word"] == "hello"
        assert data["status"] == "learning"
        assert data["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_review_word_incorrect(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.3
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.update_confidence = AsyncMock(return_value=mock_item)

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/review",
                json={"word_id": str(word_id), "correct": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(word_id)
        assert data["confidence"] == 0.3

    @pytest.mark.asyncio
    async def test_review_word_calls_store_with_correct_args(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = word_id
        mock_item.word = "hello"
        mock_item.phonetic = "/həˈloʊ/"
        mock_item.status = "learning"
        mock_item.confidence = 0.5
        mock_item.next_review_at = None

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.update_confidence = AsyncMock(return_value=mock_item)

            await client.post(
                f"/api/learners/{learner_id}/vocabulary/review",
                json={"word_id": str(word_id), "correct": True, "response_time_ms": 2000},
            )

        mock_store.update_confidence.assert_awaited_once_with(
            item_id=uuid.UUID(str(word_id)),
            correct=True,
            response_time_ms=2000,
        )
