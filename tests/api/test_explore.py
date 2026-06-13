import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.explore import ExploreFeaturePreference


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


class TestExplorePreferences:
    @pytest.mark.asyncio
    async def test_list_preferences_empty(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.get(f"/api/learners/{learner_id}/explore/preferences")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_preferences_unknown_learner_returns_404(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(None))

        response = await client.get(f"/api/learners/{learner_id}/explore/preferences")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_preference_creates_favorite(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])

        response = await client.put(
            f"/api/learners/{learner_id}/explore/preferences/cet-reading",
            json={"is_favorite": True, "priority": 240, "mark_used": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["feature_id"] == "cet-reading"
        assert data["is_favorite"] is True
        assert data["priority"] == 240
        assert data["last_used_at"] is not None
        created = mock_session.added_objects[0]
        assert isinstance(created, ExploreFeaturePreference)

    @pytest.mark.asyncio
    async def test_update_preference_modifies_existing(self, client, mock_session):
        learner_id = uuid.uuid4()
        preference = ExploreFeaturePreference(
            learner_id=learner_id,
            feature_id="essay-review",
            is_favorite=True,
            priority=100,
        )
        preference.id = uuid.uuid4()
        preference.created_at = datetime.now(timezone.utc)
        preference.updated_at = datetime.now(timezone.utc)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(preference)])

        response = await client.put(
            f"/api/learners/{learner_id}/explore/preferences/essay-review",
            json={"is_favorite": False, "priority": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False
        assert data["priority"] == 10
        assert preference.is_favorite is False
        assert preference.priority == 10
        mock_session.add.assert_not_called()
