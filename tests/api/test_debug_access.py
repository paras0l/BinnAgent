import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.api import runtime as runtime_api
from src.config import settings
from src.main import app
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter


@pytest.fixture(autouse=True)
def debug_settings_guard():
    original = (
        settings.debug_console_enabled,
        settings.debug_console_token,
        list(settings.debug_console_allowed_origins),
    )
    yield
    (
        settings.debug_console_enabled,
        settings.debug_console_token,
        settings.debug_console_allowed_origins,
    ) = original
    app.dependency_overrides.clear()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    return session


class FakeEpisodeRuntime:
    def __init__(self, db):
        self.db = db

    async def get_episode_trace(self, episode_id: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "episode": {
                "id": str(episode_id),
                "learner_id": str(uuid.uuid4()),
                "source": "test",
                "entrypoint": "debug.test",
                "status": "completed",
                "task_spec": {},
                "started_at": now,
                "created_at": now,
                "updated_at": now,
            },
            "events": [],
            "tool_calls": [],
        }


class TestDebugAccess:
    @pytest.mark.asyncio
    async def test_runtime_episode_returns_404_when_debug_console_disabled(
        self, client, mock_session
    ):
        settings.debug_console_enabled = False

        response = await client.get(f"/api/runtime/episodes/{uuid.uuid4()}")

        assert response.status_code == 404
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_episode_returns_not_found_for_wrong_token(self, client, mock_session):
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"

        response = await client.get(
            f"/api/runtime/episodes/{uuid.uuid4()}",
            headers={"X-Debug-Token": "wrong"},
        )

        assert response.status_code in {403, 404}
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_episode_allows_correct_debug_token(
        self, client, mock_session, monkeypatch
    ):
        episode_id = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        monkeypatch.setattr(runtime_api, "EpisodeRuntime", FakeEpisodeRuntime)

        response = await client.get(
            f"/api/runtime/episodes/{episode_id}",
            headers={"Authorization": "Bearer dev"},
        )

        assert response.status_code == 200
        assert response.json()["episode"]["id"] == str(episode_id)

    @pytest.mark.asyncio
    async def test_regular_learning_api_is_not_debug_gated(self, client, mock_session):
        settings.debug_console_enabled = False
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        async def refresh(instance):
            instance.id = uuid.uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh)

        response = await client.post("/api/learners", json={"nickname": "Alice"})

        assert response.status_code == 201
        assert response.json()["nickname"] == "Alice"

    @pytest.mark.asyncio
    async def test_memory_writer_internal_calls_do_not_require_debug_token(self):
        settings.debug_console_enabled = False
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        event = await MemoryWriter(session).record_event(
            MemoryEventInput(
                learner_id=uuid.uuid4(),
                event_type="practice_completed",
                skill="vocabulary",
                source_type="exercise",
                source_id="attempt-1",
            )
        )

        assert event.event_type == "practice_completed"
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
