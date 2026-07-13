import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.auth.email_verification import create_email_verification_token
from src.main import app
from src.models.learner import Learner, LearnerProfile


def _verified_token(email: str) -> str:
    return create_email_verification_token(email=email)


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
    async def test_create_learner_with_invitation_relationship(self, client, mock_session):
        inviter_id = uuid.uuid4()
        inviter = Learner(
            nickname="Inviter",
            email="inviter@example.com",
            invite_code="BINN-INVITER22",
        )
        inviter.id = inviter_id
        inviter_result = MagicMock()
        inviter_result.scalar_one_or_none.return_value = inviter
        mock_session.execute = AsyncMock(return_value=inviter_result)

        response = await client.post(
            "/api/learners",
            json={
                "nickname": " Alice ",
                "email": " ALICE@example.com ",
                "invite_code": " binn-inviter22 ",
                "verification_token": _verified_token("alice@example.com"),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["nickname"] == "Alice"
        assert "id" in data
        assert data["email"] == "alice@example.com"
        assert data["invite_code"].startswith("BINN-")
        created = mock_session.add.call_args.args[0]
        assert created.invited_by_learner_id == inviter_id
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_invite_code_is_rejected(self, client, mock_session):
        inviter_result = MagicMock()
        inviter_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3
        mock_session.execute = AsyncMock(side_effect=[inviter_result, count_result])

        response = await client.post(
            "/api/learners",
            json={
                "nickname": "Bob",
                "email": "bob@example.com",
                "invite_code": "BINN-NOTVALID2",
                "verification_token": _verified_token("bob@example.com"),
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid invitation code"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootstrap_invite_code_creates_first_learner(
        self,
        client,
        mock_session,
        monkeypatch,
    ):
        inviter_result = MagicMock()
        inviter_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        mock_session.execute = AsyncMock(side_effect=[inviter_result, count_result])
        monkeypatch.setattr("src.api.learners.settings.bootstrap_invite_code", "FIRST-USER")

        response = await client.post(
            "/api/learners",
            json={
                "nickname": "Root",
                "email": "root@example.com",
                "invite_code": "first-user",
                "verification_token": _verified_token("root@example.com"),
            },
        )

        assert response.status_code == 201
        created = mock_session.add.call_args.args[0]
        assert created.invited_by_learner_id is None

    @pytest.mark.asyncio
    async def test_create_learner_requires_email_and_invite_code(self, client, mock_session):
        response = await client.post("/api/learners", json={"nickname": "Alice"})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_learner_rejects_invalid_email(self, client, mock_session):
        response = await client.post(
            "/api/learners",
            json={"nickname": "Alice", "email": "invalid", "invite_code": "BINN-VALID2222"},
        )

        assert response.status_code == 422


class TestLookupLearners:
    @pytest.mark.asyncio
    async def test_lookup_returns_all_accounts_for_normalized_email(self, client, mock_session):
        first = Learner(nickname="Alice", email="family@example.com")
        first.id = uuid.uuid4()
        second = Learner(nickname="Bob", email="family@example.com")
        second.id = uuid.uuid4()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [first, second]
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/learners/lookup",
            json={
                "email": " FAMILY@example.com ",
                "verification_token": _verified_token("family@example.com"),
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "email": "family@example.com",
            "accounts": [
                {"id": str(first.id), "nickname": "Alice"},
                {"id": str(second.id), "nickname": "Bob"},
            ],
        }


class TestLoginLearner:
    @pytest.mark.asyncio
    async def test_login_requires_matching_email_and_selected_learner(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(
            nickname="Alice",
            email="alice@example.com",
            invite_code="BINN-ALICE22222",
        )
        learner.id = learner_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = learner
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/api/learners/login",
            json={
                "learner_id": str(learner_id),
                "email": "ALICE@example.com",
                "verification_token": _verified_token("alice@example.com"),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(learner_id)
        assert data["nickname"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert data["invite_code"] == "BINN-ALICE22222"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_does_not_create_missing_learner(self, client, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/learners/login",
            json={
                "learner_id": str(uuid.uuid4()),
                "email": "missing@example.com",
                "verification_token": _verified_token("missing@example.com"),
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found for this email"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_requires_email(self, client, mock_session):
        response = await client.post(
            "/api/learners/login",
            json={"learner_id": str(uuid.uuid4())},
        )

        assert response.status_code == 422


class TestBindLearnerEmail:
    @pytest.mark.asyncio
    async def test_legacy_learner_can_bind_required_email(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id

        result = MagicMock()
        result.scalar_one_or_none.return_value = learner
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.put(
            f"/api/learners/{learner_id}/email",
            json={
                "email": " ALICE@example.com ",
                "verification_token": _verified_token("alice@example.com"),
            },
        )

        assert response.status_code == 200
        assert response.json()["email"] == "alice@example.com"
        assert learner.email == "alice@example.com"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(learner)

    @pytest.mark.asyncio
    async def test_bound_email_cannot_be_replaced(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice", email="alice@example.com")
        learner.id = learner_id

        result = MagicMock()
        result.scalar_one_or_none.return_value = learner
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.put(
            f"/api/learners/{learner_id}/email",
            json={
                "email": "other@example.com",
                "verification_token": _verified_token("other@example.com"),
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Learner email is already bound"
        mock_session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bind_rejects_unverified_email(self, client, mock_session):
        response = await client.put(
            f"/api/learners/{uuid.uuid4()}/email",
            json={"email": "alice@example.com", "verification_token": "x" * 32},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Email verification required"


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
                "current_level": "b1",
                "target_score": 500,
                "daily_time_budget_minutes": 60,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["target_exam"] == "CET-4"
        assert data["current_level"] == "b1"
        assert data["target_score"] == 500
        assert data["daily_time_budget_minutes"] == 60
        assert data["learning_track"] == "reading"

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
            current_level="b1",
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
        assert data["current_level"] == "b1"
        assert data["target_score"] == 500
        assert data["daily_time_budget_minutes"] == 60

    @pytest.mark.asyncio
    async def test_get_profile_returns_empty_profile_for_existing_learner(self, client, mock_session):
        learner_id = uuid.uuid4()

        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = None
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner_id
        mock_session.execute = AsyncMock(side_effect=[profile_result, learner_result])

        response = await client.get(f"/api/learners/{learner_id}/profile")

        assert response.status_code == 200
        assert response.json() == {
            "learner_id": str(learner_id),
            "learning_track": "reading",
            "target_exam": None,
            "target_score": None,
            "exam_date": None,
            "current_level": None,
            "daily_time_budget_minutes": None,
            "interest_topics": [],
        }

    @pytest.mark.asyncio
    async def test_get_profile_learner_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = None
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[profile_result, learner_result])

        response = await client.get(f"/api/learners/{learner_id}/profile")

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"


class TestGetProfileReadiness:
    @pytest.mark.asyncio
    async def test_get_profile_readiness_returns_missing_fields_for_existing_learner(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (learner_id, None, None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}/profile-readiness")

        assert response.status_code == 200
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["target_exam"] is None
        assert data["current_level"] is None
        assert data["has_learning_goal"] is False
        assert data["has_current_level"] is False
        assert data["is_complete"] is False

    @pytest.mark.asyncio
    async def test_get_profile_readiness_reports_set_fields(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (learner_id, "cet4", "b1")
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}/profile-readiness")

        assert response.status_code == 200
        data = response.json()
        assert data["target_exam"] == "cet4"
        assert data["current_level"] == "b1"
        assert data["has_learning_goal"] is True
        assert data["has_current_level"] is True
        assert data["is_complete"] is True

    @pytest.mark.asyncio
    async def test_get_profile_readiness_learner_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/learners/{learner_id}/profile-readiness")

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"


class TestUpsertProfile:
    @pytest.mark.asyncio
    async def test_upsert_profile_creates_editable_goal_and_level(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[learner_result, profile_result])

        response = await client.put(
            f"/api/learners/{learner_id}/profile",
            json={
                "target_exam": "ielts",
                "current_level": "b2",
                "daily_time_budget_minutes": 45,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["target_exam"] == "ielts"
        assert data["current_level"] == "b2"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_profile_updates_existing_profile(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id
        profile = LearnerProfile(
            learner_id=learner_id,
            target_exam="cet4",
            current_level="a2",
        )

        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = learner
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = profile
        mock_session.execute = AsyncMock(side_effect=[learner_result, profile_result])

        response = await client.put(
            f"/api/learners/{learner_id}/profile",
            json={
                "target_exam": "toefl",
                "current_level": "b1",
                "daily_time_budget_minutes": 30,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["target_exam"] == "toefl"
        assert data["current_level"] == "b1"
        assert profile.target_exam == "toefl"
        assert profile.current_level == "b1"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_profile_learner_not_found(self, client, mock_session):
        learner_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.put(
            f"/api/learners/{learner_id}/profile",
            json={"target_exam": "gaokao", "current_level": "b1"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"
