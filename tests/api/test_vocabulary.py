import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import deps
from src.main import app


@pytest.fixture
def mock_session():
    """Override get_db_session with a controlled mock session."""
    session = AsyncMock()
    learner_result = MagicMock()
    learner_result.scalar_one_or_none.return_value = uuid.uuid4()
    session.execute = AsyncMock(return_value=learner_result)
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


class TestListVocabulary:
    @pytest.mark.asyncio
    async def test_list_vocabulary_returns_words(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()
        last_reviewed_at = datetime(2026, 6, 13, 8, 30, tzinfo=timezone.utc)
        next_review_at = datetime(2026, 6, 14, 8, 30, tzinfo=timezone.utc)

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner_id

        item = MagicMock()
        item.id = word_id
        item.word = "significant"
        item.phonetic = "/sɪɡˈnɪfɪkənt/"
        item.status = "learning"
        item.confidence = 0.65
        item.review_count = 3
        item.meanings = [{"definition": "important or noticeable"}]
        item.last_reviewed_at = last_reviewed_at
        item.next_review_at = next_review_at

        vocabulary_result = MagicMock()
        vocabulary_result.scalars.return_value.all.return_value = [item]
        mock_session.execute.side_effect = [learner_result, vocabulary_result]

        response = await client.get(f"/api/learners/{learner_id}/vocabulary")

        assert response.status_code == 200
        data = response.json()
        assert data == [
            {
                "id": str(word_id),
                "word": "significant",
                "phonetic": "/sɪɡˈnɪfɪkənt/",
                "status": "learning",
                "confidence": 0.65,
                "review_count": 3,
                "meaning": "important or noticeable",
                "last_reviewed_at": last_reviewed_at.isoformat(),
                "next_review_at": next_review_at.isoformat(),
            }
        ]

    @pytest.mark.asyncio
    async def test_list_vocabulary_empty(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner_id

        vocabulary_result = MagicMock()
        vocabulary_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [learner_result, vocabulary_result]

        response = await client.get(f"/api/learners/{learner_id}/vocabulary")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_vocabulary_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        response = await client.get(f"/api/learners/{uuid.uuid4()}/vocabulary")

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"


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

    @pytest.mark.asyncio
    async def test_add_word_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            response = await client.post(
                f"/api/learners/{uuid.uuid4()}/vocabulary/add",
                json={"word": "hello"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"
        MockStore.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_word_blank_word_returns_422(self, client, mock_session):
        response = await client.post(
            f"/api/learners/{uuid.uuid4()}/vocabulary/add",
            json={"word": "   "},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_word_invalid_word_returns_422(self, client, mock_session):
        learner_id = uuid.uuid4()

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.add_word = AsyncMock(side_effect=ValueError("invalid"))

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/add",
                json={"word": "not a single word"},
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "Invalid vocabulary word"


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

    @pytest.mark.asyncio
    async def test_get_due_reviews_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            response = await client.get(f"/api/learners/{uuid.uuid4()}/vocabulary/due")

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"
        MockStore.assert_not_called()


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
            learner_id=learner_id,
            item_id=uuid.UUID(str(word_id)),
            correct=True,
            response_time_ms=2000,
        )

    @pytest.mark.asyncio
    async def test_review_word_invalid_word_id_returns_422(self, client, mock_session):
        learner_id = uuid.uuid4()

        response = await client.post(
            f"/api/learners/{learner_id}/vocabulary/review",
            json={"word_id": "not-a-uuid", "correct": True},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_review_word_negative_response_time_returns_422(self, client, mock_session):
        response = await client.post(
            f"/api/learners/{uuid.uuid4()}/vocabulary/review",
            json={"word_id": str(uuid.uuid4()), "correct": True, "response_time_ms": -1},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_review_word_not_found_returns_404(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.update_confidence = AsyncMock(side_effect=ValueError("not found"))

            response = await client.post(
                f"/api/learners/{learner_id}/vocabulary/review",
                json={"word_id": str(word_id), "correct": True},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Vocabulary item not found"

    @pytest.mark.asyncio
    async def test_review_word_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            response = await client.post(
                f"/api/learners/{uuid.uuid4()}/vocabulary/review",
                json={"word_id": str(uuid.uuid4()), "correct": True},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"
        MockStore.assert_not_called()


class TestDeleteWord:
    @pytest.mark.asyncio
    async def test_delete_word(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.delete_word = AsyncMock()

            response = await client.delete(
                f"/api/learners/{learner_id}/vocabulary/{word_id}"
            )

        assert response.status_code == 204
        mock_store.delete_word.assert_awaited_once_with(
            learner_id=learner_id,
            item_id=word_id,
        )

    @pytest.mark.asyncio
    async def test_delete_word_not_found_returns_404(self, client, mock_session):
        learner_id = uuid.uuid4()
        word_id = uuid.uuid4()

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.delete_word = AsyncMock(side_effect=ValueError("not found"))

            response = await client.delete(
                f"/api/learners/{learner_id}/vocabulary/{word_id}"
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Vocabulary item not found"

    @pytest.mark.asyncio
    async def test_delete_word_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        with patch("src.api.vocabulary.VocabularyStore") as MockStore:
            response = await client.delete(
                f"/api/learners/{uuid.uuid4()}/vocabulary/{uuid.uuid4()}"
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"
        MockStore.assert_not_called()
