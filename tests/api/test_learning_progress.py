import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.learning_progress import LearningProgressItem


@pytest.fixture
def mock_session():
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)
    session.flush = AsyncMock()

    async def _refresh(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        if getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)
        if getattr(instance, "updated_at", None) is None:
            instance.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)
    session.added_objects = added_objects
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


class TestLearningProgress:
    @pytest.mark.asyncio
    async def test_list_progress_empty(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.get(
            f"/api/learners/{learner_id}/learning-progress?skill=grammar"
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_unknown_learner_returns_404(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(None))

        response = await client.get(f"/api/learners/{learner_id}/learning-progress")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upsert_opened_progress_creates_item(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])

        response = await client.put(
            f"/api/learners/{learner_id}/learning-progress/pronunciation/iː",
            json={
                "title": "/iː/ long e",
                "mark_opened": True,
                "metadata": {"symbol": "/iː/", "category": "vowel"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skill"] == "pronunciation"
        assert data["item_id"] == "iː"
        assert data["title"] == "/iː/ long e"
        assert data["opened_count"] == 1
        assert data["last_opened_at"] is not None
        assert data["metadata"] == {"symbol": "/iː/", "category": "vowel"}
        created = mock_session.added_objects[0]
        assert isinstance(created, LearningProgressItem)

    @pytest.mark.asyncio
    async def test_upsert_learned_progress_marks_learned(self, client, mock_session):
        learner_id = uuid.uuid4()
        item = LearningProgressItem(
            learner_id=learner_id,
            skill="grammar",
            item_id="present-for-future",
            title="主将从现",
            status="opened",
            opened_count=2,
        )
        item.id = uuid.uuid4()
        item.created_at = datetime.now(timezone.utc)
        item.updated_at = datetime.now(timezone.utc)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(item)])

        response = await client.put(
            f"/api/learners/{learner_id}/learning-progress/grammar/present-for-future",
            json={"mark_learned": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "learned"
        assert data["learned_at"] is not None
        assert item.status == "learned"

    @pytest.mark.asyncio
    async def test_favorite_toggle_persists(self, client, mock_session):
        learner_id = uuid.uuid4()
        item = LearningProgressItem(
            learner_id=learner_id,
            skill="grammar",
            item_id="because-because-of",
            title="because 与 because of",
            status="opened",
            is_favorite=False,
        )
        item.id = uuid.uuid4()
        item.created_at = datetime.now(timezone.utc)
        item.updated_at = datetime.now(timezone.utc)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(item)])

        response = await client.put(
            f"/api/learners/{learner_id}/learning-progress/grammar/because-because-of",
            json={"is_favorite": True},
        )

        assert response.status_code == 200
        assert response.json()["is_favorite"] is True
        assert item.is_favorite is True
