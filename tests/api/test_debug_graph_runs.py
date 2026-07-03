import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import debug as debug_api
from src.api import deps
from src.config import settings
from src.main import app
from src.models.learner import Learner
from src.models.runtime import AgentEpisode
from src.runtime.schemas import AgentEpisodeView, EpisodeTraceView


@pytest.fixture(autouse=True)
def debug_graph_run_settings_guard():
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


def _count(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
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
                started_at=now,
                completed_at=now,
                created_at=now,
                updated_at=now,
            ),
            events=[],
            tool_calls=[],
            checkpoint={"checkpoint_id": str(uuid.uuid4()), "status": "completed"},
            verification_report={"status": "passed", "checks": []},
            graph_run={"graph_run_id": "graph-run-1", "thread_id": f"daily-lesson:{episode_id}"},
            prompt_executions=[],
            evidence_refs=[],
            node_summaries=[],
        )


@pytest.mark.asyncio
async def test_debug_graph_run_requires_debug_access(client, mock_session) -> None:
    settings.debug_console_enabled = False

    response = await client.get(f"/api/debug/graph-runs/{uuid.uuid4()}")

    assert response.status_code == 404
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_debug_graph_run_does_not_bypass_learner_scope(
    client,
    mock_session,
) -> None:
    learner_id = uuid.uuid4()
    other_learner_id = uuid.uuid4()
    episode_id = uuid.uuid4()
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

    response = await client.get(
        f"/api/debug/graph-runs/{episode_id}",
        params={"learner_id": str(other_learner_id)},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_debug_graph_run_returns_empty_prompt_executions(
    client,
    mock_session,
    monkeypatch,
) -> None:
    learner_id = uuid.uuid4()
    episode_id = uuid.uuid4()
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
    monkeypatch.setattr(debug_api, "EpisodeRuntime", FakeEpisodeRuntime)

    response = await client.get(
        f"/api/debug/graph-runs/{episode_id}",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == str(episode_id)
    assert data["prompt_executions"] == []
    assert data["verification_report"]["status"] == "passed"


@pytest.mark.asyncio
async def test_debug_graph_runs_list_is_learner_scoped(client, mock_session) -> None:
    learner_id = uuid.uuid4()
    episode_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    learner = Learner(nickname="Alice")
    learner.id = learner_id
    episode = AgentEpisode(
        learner_id=learner_id,
        source="recommendation",
        entrypoint="daily_lesson.start",
        status="completed",
        task_spec={},
        context_snapshot={"thread_id": f"daily-lesson:{episode_id}", "graph_run_id": "run-1"},
        verification_report={"status": "passed"},
        started_at=now,
        completed_at=now,
    )
    episode.id = episode_id
    episode.created_at = now
    episode.updated_at = now
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    mock_session.execute = AsyncMock(side_effect=[_one(learner), _count(1), _many([episode])])

    response = await client.get(
        "/api/debug/graph-runs",
        params={"learner_id": str(learner_id)},
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["graph_runs"][0]["graph_run_id"] == "run-1"
