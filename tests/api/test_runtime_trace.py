import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.api import runtime as runtime_api
from src.config import settings
from src.main import app
from src.models.learner import Learner
from src.models.runtime import AgentEpisode
from src.runtime.events import LearningEventView
from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView


@pytest.fixture(autouse=True)
def runtime_trace_settings_guard():
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


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class FakeEpisodeRuntime:
    def __init__(self, db):
        self.db = db

    async def get_episode_trace(self, episode_id: uuid.UUID) -> EpisodeTraceView:
        now = datetime.now(timezone.utc)
        return EpisodeTraceView(
            episode=AgentEpisodeView(
                id=str(episode_id),
                learner_id=str(uuid.uuid4()),
                source="recommendation",
                entrypoint="daily_lesson.start",
                status="completed",
                task_spec={"task_id": "task-1"},
                verification_report={"status": "passed", "checks": []},
                started_at=now,
                completed_at=now,
                created_at=now,
                updated_at=now,
            ),
            events=[
                LearningEventView(
                    id=str(uuid.uuid4()),
                    episode_id=str(episode_id),
                    learner_id=str(uuid.uuid4()),
                    event_type="verification_report_generated",
                    source_module="daily_lesson",
                    payload={},
                    occurred_at=now,
                )
            ],
            tool_calls=[],
            checkpoint={"checkpoint_id": str(uuid.uuid4()), "status": "completed"},
            verification_report={"status": "passed", "checks": []},
            prompt_executions=[],
            evidence_refs=[],
            node_summaries=[],
        )


@pytest.mark.asyncio
async def test_runtime_episode_trace_alias_returns_enriched_trace(
    client,
    mock_session,
    monkeypatch,
) -> None:
    episode_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    learner = Learner(nickname="Alice")
    learner.id = learner_id
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="completed",
        task_spec={},
        started_at=now,
    )
    episode.id = episode_id
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    mock_session.execute = AsyncMock(side_effect=[_one(episode), _one(learner)])
    monkeypatch.setattr(runtime_api, "EpisodeRuntime", FakeEpisodeRuntime)

    response = await client.get(
        f"/api/runtime/episodes/{episode_id}/trace",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verification_report"]["status"] == "passed"
    assert data["checkpoint"]["status"] == "completed"
    assert data["prompt_executions"] == []
