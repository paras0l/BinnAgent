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
        mock_session.add.assert_called_once()
        assert mock_session.commit.await_count >= 1
        mock_ainvoke.assert_awaited_once()

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
