import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.learner import Learner, LearnerProfile


@pytest.fixture
def mock_session():
    """Override get_db_session with a controlled mock session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def _refresh(instance):
        """Simulate DB refresh: populate server/default values."""
        if hasattr(instance, "id") and instance.id is None:
            instance.id = uuid.uuid4()

    session.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


class TestCreateLearner:
    @pytest.mark.asyncio
    async def test_create_learner(self, client, mock_session):
        response = await client.post("/api/learners", json={"nickname": "Alice"})

        assert response.status_code == 201
        data = response.json()
        assert data["nickname"] == "Alice"
        assert "id" in data
        assert data["email"] is None
        # Verify the session was called
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_learner_with_email(self, client, mock_session):
        response = await client.post(
            "/api/learners",
            json={"nickname": "Bob", "email": "bob@example.com"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["nickname"] == "Bob"
        assert data["email"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_create_learner_missing_nickname(self, client, mock_session):
        response = await client.post("/api/learners", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_learner_blank_nickname_returns_422(self, client, mock_session):
        response = await client.post("/api/learners", json={"nickname": "   "})

        assert response.status_code == 422


class TestGetLearner:
    @pytest.mark.asyncio
    async def test_get_learner(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice", email="alice@example.com")
        learner.id = learner_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = learner
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(learner_id)
        assert data["nickname"] == "Alice"
        assert data["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_get_learner_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"


class TestCreateProfile:
    @pytest.mark.asyncio
    async def test_create_profile(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id

        # First execute call: verify learner exists
        # Second execute call: check no existing profile
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner
        none_result = MagicMock()
        none_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[learner_result, none_result])

        response = await client.post(
            f"/api/learners/{learner_id}/profile",
            json={
                "target_exam": "CET-4",
                "target_score": 500,
                "daily_time_budget_minutes": 60,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["target_exam"] == "CET-4"
        assert data["target_score"] == 500
        assert data["daily_time_budget_minutes"] == 60

    @pytest.mark.asyncio
    async def test_create_profile_learner_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            f"/api/learners/{learner_id}/profile",
            json={"target_exam": "CET-6"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"

    @pytest.mark.asyncio
    async def test_create_profile_already_exists(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id
        existing_profile = LearnerProfile(learner_id=learner_id)

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = existing_profile
        mock_session.execute = AsyncMock(side_effect=[learner_result, profile_result])

        response = await client.post(
            f"/api/learners/{learner_id}/profile",
            json={"target_exam": "CET-6"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Profile already exists"

    @pytest.mark.asyncio
    async def test_create_profile_invalid_score_returns_422(self, client, mock_session):
        response = await client.post(
            f"/api/learners/{uuid.uuid4()}/profile",
            json={"target_score": 999},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_profile_invalid_time_budget_returns_422(self, client, mock_session):
        response = await client.post(
            f"/api/learners/{uuid.uuid4()}/profile",
            json={"daily_time_budget_minutes": 0},
        )

        assert response.status_code == 422


class TestGetProfile:
    @pytest.mark.asyncio
    async def test_get_profile(self, client, mock_session):
        learner_id = uuid.uuid4()
        profile = LearnerProfile(
            learner_id=learner_id,
            target_exam="CET-4",
            target_score=500,
            daily_time_budget_minutes=60,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = profile
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["target_exam"] == "CET-4"
        assert data["target_score"] == 500
        assert data["daily_time_budget_minutes"] == 60

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}/profile")

        assert response.status_code == 404
        assert response.json()["detail"] == "Profile not found"
