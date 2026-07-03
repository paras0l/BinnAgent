import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.api import deps
from src.config import settings
from src.main import app
from src.models.learner import Learner
from src.models.runtime import AgentEpisode
from src.security.ownership import get_attempt_for_learner, get_learner_for_user


@pytest.fixture
def mock_session():
    original_debug_settings = (
        settings.debug_console_enabled,
        settings.debug_console_token,
        list(settings.debug_console_allowed_origins),
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    (
        settings.debug_console_enabled,
        settings.debug_console_token,
        settings.debug_console_allowed_origins,
    ) = original_debug_settings
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _learner(learner_id: uuid.UUID, owner_user_id: uuid.UUID) -> Learner:
    learner = Learner(nickname=f"learner-{learner_id.hex[:6]}", tenant_id=owner_user_id)
    learner.id = learner_id
    return learner


def _episode(episode_id: uuid.UUID, learner_id: uuid.UUID) -> AgentEpisode:
    episode = AgentEpisode(
        learner_id=learner_id,
        source="daily_lesson",
        entrypoint="daily_lesson.start",
        status="waiting_user",
        task_spec={},
        started_at=datetime.now(timezone.utc),
    )
    episode.id = episode_id
    return episode


class TestLearnerScopeIsolation:
    @pytest.mark.asyncio
    async def test_learner_b_cannot_read_learner_a_runtime_trace(
        self,
        client,
        mock_session,
    ):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        learner_a = uuid.uuid4()
        episode_id = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(_episode(episode_id, learner_a)),
                _one(_learner(learner_a, user_a)),
            ]
        )

        response = await client.get(
            f"/api/runtime/episodes/{episode_id}",
            headers={"X-Debug-Token": "dev", "X-User-Id": str(user_b)},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_learner_b_cannot_submit_answer_to_learner_a_episode(
        self,
        client,
        mock_session,
    ):
        user_b = uuid.uuid4()
        learner_b = uuid.uuid4()
        learner_a_episode = uuid.uuid4()
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(_learner(learner_b, user_b)),
                _one(None),
            ]
        )

        response = await client.post(
            f"/api/learners/{learner_b}/daily-lessons/{learner_a_episode}/answer",
            headers={"X-User-Id": str(user_b)},
            json={"answer": "B should not be able to answer this."},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_learner_b_cannot_read_learner_a_memory_summary(
        self,
        client,
        mock_session,
    ):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        learner_a = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(_learner(learner_a, user_a)))

        response = await client.get(
            f"/api/learners/{learner_a}/memory/summary",
            headers={"X-User-Id": str(user_b)},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_learner_b_cannot_patch_learner_a_memory_event(
        self,
        client,
        mock_session,
    ):
        user_b = uuid.uuid4()
        learner_b = uuid.uuid4()
        memory_a = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(_learner(learner_b, user_b)),
                _one(None),
            ]
        )

        response = await client.patch(
            f"/api/learners/{learner_b}/memory/items/learning_memory_event/{memory_a}",
            headers={"X-Debug-Token": "dev", "X-User-Id": str(user_b)},
            json={"operation": "delete"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_learner_b_cannot_modify_learner_a_explore_preference(
        self,
        client,
        mock_session,
    ):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        learner_a = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(_learner(learner_a, user_a)))

        response = await client.put(
            f"/api/learners/{learner_a}/explore/preferences/grammar-explain",
            headers={"X-User-Id": str(user_b)},
            json={"is_favorite": True},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_debug_token_alone_cannot_read_owned_runtime_trace(
        self,
        client,
        mock_session,
    ):
        user_a = uuid.uuid4()
        learner_a = uuid.uuid4()
        episode_id = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(_episode(episode_id, learner_a)),
                _one(_learner(learner_a, user_a)),
            ]
        )

        response = await client.get(
            f"/api/runtime/episodes/{episode_id}",
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_scoped_helpers_return_403_or_404_for_cross_scope_resources(self):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        learner_a = uuid.uuid4()

        learner_session = AsyncMock()
        learner_session.execute = AsyncMock(return_value=_one(_learner(learner_a, user_a)))
        with pytest.raises(HTTPException) as denied:
            await get_learner_for_user(learner_session, user_b, learner_a)
        assert denied.value.status_code == 403

        attempt_session = AsyncMock()
        attempt_session.execute = AsyncMock(return_value=_one(None))
        with pytest.raises(HTTPException) as not_found:
            await get_attempt_for_learner(attempt_session, learner_a, uuid.uuid4())
        assert not_found.value.status_code == 404
