import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import deps
from src.main import app


@pytest.fixture
def mock_session():
    """Override get_db_session with a controlled mock session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    learner_result = MagicMock()
    learner_result.scalar_one_or_none.return_value = uuid.uuid4()
    session.execute = AsyncMock(return_value=learner_result)

    async def _refresh(instance):
        if hasattr(instance, "id") and instance.id is None:
            instance.id = uuid.uuid4()

    session.refresh = AsyncMock(side_effect=_refresh)

    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


class TestStartSession:
    @pytest.mark.asyncio
    @patch("src.api.sessions.daily_lesson_graph.ainvoke")
    async def test_start_session(self, mock_ainvoke, client, mock_session):
        learner_id = uuid.uuid4()
        mock_ainvoke.return_value = {
            "active_skill": "vocabulary",
            "today_goal": "Learn 20 new CET-6 words",
        }

        response = await client.post(
            "/api/sessions/start",
            json={"learner_id": str(learner_id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["active_skill"] == "vocabulary"
        assert data["today_goal"] == "Learn 20 new CET-6 words"
        assert "id" in data
        assert mock_session.add.call_count >= 1
        assert mock_session.commit.await_count >= 1
        mock_ainvoke.assert_awaited_once()
        graph_config = mock_ainvoke.await_args.kwargs["config"]
        assert graph_config["configurable"]["thread_id"]

    @pytest.mark.asyncio
    @patch("src.api.sessions.daily_lesson_graph.ainvoke")
    async def test_start_session_with_custom_message(self, mock_ainvoke, client, mock_session):
        learner_id = uuid.uuid4()
        mock_ainvoke.return_value = {
            "active_skill": "reading",
            "today_goal": "Read and analyze a passage",
        }

        response = await client.post(
            "/api/sessions/start",
            json={
                "learner_id": str(learner_id),
                "user_message": "I want to practice reading today",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["active_skill"] == "reading"
        assert data["today_goal"] == "Read and analyze a passage"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_start_session_invalid_payload(self, client):
        response = await client.post(
            "/api/sessions/start",
            json={},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_start_session_invalid_learner_id_returns_422(self, client):
        response = await client.post(
            "/api/sessions/start",
            json={"learner_id": "not-a-uuid"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_start_session_unknown_learner_returns_404(self, client, mock_session):
        learner_result = MagicMock()
        learner_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = learner_result

        response = await client.post(
            "/api/sessions/start",
            json={"learner_id": str(uuid.uuid4())},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Learner not found"

    @pytest.mark.asyncio
    @patch("src.api.sessions.daily_lesson_graph.ainvoke")
    async def test_start_session_marks_session_failed_when_graph_fails(
        self, mock_ainvoke, client, mock_session
    ):
        mock_ainvoke.side_effect = RuntimeError("graph exploded")

        response = await client.post(
            "/api/sessions/start",
            json={"learner_id": str(uuid.uuid4())},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to start learning session"
        session = mock_session.add.call_args.args[0]
        assert session.status == "failed"
        assert session.summary == "graph exploded"
        assert mock_session.commit.await_count >= 2
