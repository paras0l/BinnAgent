import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import debug as debug_api
from src.api import deps
from src.api import memory as memory_api
from src.api import runtime as runtime_api
from src.config import settings
from src.main import app
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.learner import Learner, LearnerProfile
from src.models.runtime import AgentEpisode


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


class FakeMemoryCurator:
    def __init__(self, db):
        self.db = db

    async def curate_learner(self, learner_id: uuid.UUID) -> dict:
        return {
            "event_count": 1,
            "episode_count": 1,
            "learner_model_count": 0,
            "teaching_strategy_count": 0,
            "reflection_layer": "episode",
            "read_layers": ["event"],
            "updated_layers": ["episode"],
            "active_weaknesses": [],
        }


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


def _rows(values: list):
    result = MagicMock()
    result.all.return_value = values
    return result


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
    @pytest.mark.parametrize(
        "path",
        [
            "/api/debug/learners",
            "/api/runtime/episodes",
        ],
    )
    async def test_debug_list_endpoints_return_404_when_debug_console_disabled(
        self, client, mock_session, path
    ):
        settings.debug_console_enabled = False

        response = await client.get(path)

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
    @pytest.mark.parametrize(
        "path",
        [
            "/api/debug/learners",
            "/api/runtime/episodes",
        ],
    )
    async def test_debug_list_endpoints_return_not_found_for_wrong_token(
        self, client, mock_session, path
    ):
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"

        response = await client.get(path, headers={"X-Debug-Token": "wrong"})

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
    async def test_debug_learners_allows_correct_debug_token(self, client, mock_session):
        learner_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        learner = Learner(nickname="Alice", email="alice@example.com")
        learner.id = learner_id
        learner.created_at = now
        learner.updated_at = now
        profile = LearnerProfile(
            learner_id=learner_id,
            target_exam="CET6",
            current_level="intermediate",
            daily_time_budget_minutes=30,
        )
        profile.id = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(
            side_effect=[
                _count(1),
                _rows([(learner, profile, 3, 4, 5, 6)]),
            ]
        )

        response = await client.get(
            "/api/debug/learners",
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["learners"][0]["id"] == str(learner_id)
        assert data["learners"][0]["profile"]["target_exam"] == "CET6"
        assert data["learners"][0]["counts"] == {
            "episode_count": 3,
            "memory_event_count": 4,
            "exercise_attempt_count": 5,
            "vocabulary_count": 6,
        }

    @pytest.mark.asyncio
    async def test_runtime_episode_list_allows_correct_debug_token_and_counts(
        self, client, mock_session
    ):
        learner_id = uuid.uuid4()
        episode_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        episode = AgentEpisode(
            learner_id=learner_id,
            source="daily_lesson",
            entrypoint="daily.start",
            status="completed",
            task_spec={
                "task_type": "knowledge_practice",
                "objective": "Practice present perfect",
                "target": {"target_type": "curriculum_node", "target_id": "node-1"},
            },
            verification_report={"status": "passed"},
            started_at=now,
            completed_at=now,
        )
        episode.id = episode_id
        episode.created_at = now
        episode.updated_at = now
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(
            side_effect=[
                _count(1),
                _rows([(episode, "Alice", 7, 2)]),
            ]
        )

        response = await client.get(
            "/api/runtime/episodes",
            params={"learner_id": str(learner_id)},
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["episodes"][0]["id"] == str(episode_id)
        assert data["episodes"][0]["learner_id"] == str(learner_id)
        assert data["episodes"][0]["task_type"] == "knowledge_practice"
        assert data["episodes"][0]["target_type"] == "curriculum_node"
        assert data["episodes"][0]["event_count"] == 7
        assert data["episodes"][0]["tool_call_count"] == 2
        assert data["episodes"][0]["verification_status"] == "passed"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "json_body"),
        [
            ("POST", "/api/learners/{learner_id}/memory/curate", None),
            (
                "PATCH",
                "/api/learners/{learner_id}/memory/items/learning_memory_event/{target_id}",
                {"operation": "delete"},
            ),
            ("GET", "/api/learners/{learner_id}/memory/export", None),
            ("POST", "/api/learners/{learner_id}/memory/reset-plan", None),
            ("GET", "/api/learners/{learner_id}/memory/settings", None),
            (
                "PATCH",
                "/api/learners/{learner_id}/memory/settings",
                {"emotion_rhythm_enabled": False},
            ),
        ],
    )
    async def test_memory_debug_endpoints_return_404_when_debug_disabled(
        self, client, mock_session, method, path, json_body
    ):
        settings.debug_console_enabled = False
        request_path = path.format(learner_id=uuid.uuid4(), target_id=uuid.uuid4())

        response = await client.request(method, request_path, json=json_body)

        assert response.status_code == 404
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_debug_endpoint_returns_not_found_for_wrong_token(
        self, client, mock_session
    ):
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"

        response = await client.post(
            f"/api/learners/{uuid.uuid4()}/memory/reset-plan",
            headers={"X-Debug-Token": "wrong"},
        )

        assert response.status_code in {403, 404}
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_debug_endpoint_allows_correct_debug_token(
        self, client, mock_session, monkeypatch
    ):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        mock_session.execute = AsyncMock(side_effect=[_one(learner)])
        mock_session.flush = AsyncMock()
        monkeypatch.setattr(memory_api, "MemoryCurator", FakeMemoryCurator)

        response = await client.post(
            f"/api/learners/{learner_id}/memory/curate",
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 200
        assert response.json()["event_count"] == 1

    @pytest.mark.asyncio
    async def test_memory_summary_is_not_debug_gated(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice")
        learner.id = learner_id
        settings.debug_console_enabled = False
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(learner),
                _many([]),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _many([]),
                _many([]),
                _many([]),
                _many([]),
            ]
        )

        response = await client.get(f"/api/learners/{learner_id}/memory/summary")

        assert response.status_code == 200
        assert response.json()["learner"]["nickname"] == "Alice"

    @pytest.mark.asyncio
    async def test_debug_rag_search_allows_correct_debug_token(
        self, client, mock_session, monkeypatch
    ):
        chunk_id = uuid.uuid4()
        source_id = uuid.uuid4()
        node_id = uuid.uuid4()
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"

        async def fake_retrieve_chunks(db, model_router, **kwargs):
            assert db is mock_session
            assert kwargs["query"] == "present perfect"
            return [
                SimpleNamespace(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    curriculum_node_id=node_id,
                    page_number=12,
                    content="Present perfect connects past experience to now.",
                    score=0.87,
                    retrieval_mode="vector",
                    embedding_model="nomic-embed-text:latest",
                    chunk_version="pypdf-page-v1",
                    source_version="v1",
                )
            ]

        monkeypatch.setattr(debug_api, "retrieve_chunks", fake_retrieve_chunks)

        response = await client.get(
            "/api/debug/rag/search",
            params={"query": "present perfect"},
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["retrieval_mode"] == "vector"
        assert data["result_count"] == 1
        assert data["results"][0]["chunk_id"] == str(chunk_id)

    @pytest.mark.asyncio
    async def test_debug_simulation_latest_report_reads_report_file(
        self, client, mock_session, monkeypatch, tmp_path
    ):
        settings.debug_console_enabled = True
        settings.debug_console_token = "dev"
        monkeypatch.setattr(debug_api, "SIMULATION_REPORT_ROOT", tmp_path)
        (tmp_path / "latest_report.json").write_text(
            """
            {
              "run_id": "sim_test",
              "status": "failed",
              "steps": [
                {"name": "answer", "status": "failed", "failures": ["expected passed"]}
              ],
              "runtime_metrics": {
                "episode_count": 2,
                "completed_episode_count": 1,
                "failed_episode_count": 1,
                "verification_pass_count": 1,
                "verification_fail_count": 1,
                "avg_tool_latency_ms": 25.5
              },
              "failures": []
            }
            """,
            encoding="utf-8",
        )

        response = await client.get(
            "/api/debug/simulation/reports/latest",
            headers={"X-Debug-Token": "dev"},
        )

        assert response.status_code == 200
        summary = response.json()["summary"]
        assert summary["status"] == "failed"
        assert summary["episode_count"] == 2
        assert summary["failed_assertion_count"] == 1

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
