import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api import deps
from src.main import app
from src.models.learner import Learner
from src.models.vocabulary import VocabularyItem


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def _refresh(instance):
        if hasattr(instance, "id") and instance.id is None:
            instance.id = uuid.uuid4()

    session.refresh = AsyncMock(side_effect=_refresh)
    session.commit = AsyncMock()

    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _make_vocab_mock(
    word: str = "abandon",
    phonetic: str = "/əˈbændən/",
    status: str = "learning",
    confidence: float = 0.5,
) -> MagicMock:
    item = MagicMock(spec=VocabularyItem)
    item.id = uuid.uuid4()
    item.word = word
    item.phonetic = phonetic
    item.status = status
    item.confidence = confidence
    item.next_review_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return item


class TestFullLearningSession:
    @pytest.mark.asyncio
    async def test_full_flow(self, mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/learners",
                json={"nickname": "Test User", "email": "test@example.com"},
            )
            assert resp.status_code == 201, f"Create learner failed: {resp.text}"
            learner_data = resp.json()
            learner_id = learner_data["id"]
            assert learner_data["nickname"] == "Test User"
            assert learner_data["email"] == "test@example.com"

            mock_graph_result = {
                "active_skill": "reading",
                "today_goal": "练习六级阅读中的转折定位题",
                "messages": [{"role": "assistant", "content": "Session complete"}],
            }

            with patch(
                "src.api.sessions.daily_lesson_graph.ainvoke",
                new_callable=AsyncMock,
                return_value=mock_graph_result,
            ):
                resp = await client.post(
                    "/api/sessions/start",
                    json={
                        "learner_id": learner_id,
                        "user_message": "我想练习六级阅读",
                    },
                )
                assert resp.status_code == 200, f"Start session failed: {resp.text}"
                session_data = resp.json()
                assert session_data["status"] == "completed"
                assert session_data["active_skill"] == "reading"
                assert session_data["today_goal"] == "练习六级阅读中的转折定位题"
                assert "id" in session_data

            word_item = _make_vocab_mock(
                word="abandon",
                phonetic="/əˈbændən/",
                status="learning",
                confidence=0.5,
            )
            mock_store = AsyncMock()
            mock_store.add_word = AsyncMock(return_value=word_item)
            mock_store.get_due_reviews = AsyncMock(return_value=[word_item])
            reviewed_item = _make_vocab_mock(
                word="abandon",
                phonetic="/əˈbændən/",
                status="reviewed",
                confidence=0.7,
            )
            mock_store.update_confidence = AsyncMock(return_value=reviewed_item)

            with patch("src.api.vocabulary.VocabularyStore", return_value=mock_store):
                resp = await client.post(
                    f"/api/learners/{learner_id}/vocabulary/add",
                    json={
                        "word": "abandon",
                        "phonetic": "/əˈbændən/",
                        "level": "CET6",
                        "meanings": ["放弃", "遗弃"],
                    },
                )
                assert resp.status_code == 200, f"Add word failed: {resp.text}"
                word_data = resp.json()
                assert word_data["word"] == "abandon"
                assert word_data["status"] == "learning"
                assert word_data["confidence"] == 0.5
                word_id = word_data["id"]

            with patch("src.api.vocabulary.VocabularyStore", return_value=mock_store):
                resp = await client.get(f"/api/learners/{learner_id}/vocabulary/due")
                assert resp.status_code == 200, f"Get due reviews failed: {resp.text}"
                due_list = resp.json()
                assert len(due_list) >= 1
                assert due_list[0]["word"] == "abandon"

            with patch("src.api.vocabulary.VocabularyStore", return_value=mock_store):
                review_word_id = str(reviewed_item.id) if hasattr(reviewed_item, "id") else word_id
                resp = await client.post(
                    f"/api/learners/{learner_id}/vocabulary/review",
                    json={
                        "word_id": review_word_id,
                        "correct": True,
                        "response_time_ms": 2500,
                    },
                )
                assert resp.status_code == 200, f"Submit review failed: {resp.text}"
                review_data = resp.json()
                assert review_data["status"] == "reviewed"
                assert review_data["confidence"] == 0.7

            resp = await client.get("/health")
            assert resp.status_code == 200
            health_data = resp.json()
            assert health_data["status"] == "ok"
            assert health_data["version"] == "0.1.0"


class TestLearnerCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_learner(self, mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/learners",
                json={"nickname": "Alice", "email": "alice@example.com"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["nickname"] == "Alice"
            assert data["email"] == "alice@example.com"
            learner_id = data["id"]

            learner_obj = Learner(nickname="Alice", email="alice@example.com")
            learner_obj.id = uuid.UUID(learner_id)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = learner_obj
            mock_session.execute = AsyncMock(return_value=mock_result)

            resp = await client.get(f"/api/learners/{learner_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == learner_id
            assert data["nickname"] == "Alice"
            assert data["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_get_learner_not_found(self, mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            learner_id = uuid.uuid4()

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            resp = await client.get(f"/api/learners/{learner_id}")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Learner not found"

    @pytest.mark.asyncio
    async def test_create_and_get_profile(self, mock_session):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/learners",
                json={"nickname": "Bob"},
            )
            assert resp.status_code == 201
            learner_id = resp.json()["id"]

            learner_obj = Learner(nickname="Bob")
            learner_obj.id = uuid.UUID(learner_id)

            learner_result = MagicMock()
            learner_result.scalar_one_or_none.return_value = learner_obj
            none_result = MagicMock()
            none_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(side_effect=[learner_result, none_result])

            resp = await client.post(
                f"/api/learners/{learner_id}/profile",
                json={
                    "target_exam": "CET-6",
                    "target_score": 550,
                    "daily_time_budget_minutes": 45,
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["learner_id"] == learner_id
            assert data["target_exam"] == "CET-6"
            assert data["target_score"] == 550
            assert data["daily_time_budget_minutes"] == 45

            from src.models.learner import LearnerProfile

            profile_obj = LearnerProfile(
                learner_id=uuid.UUID(learner_id),
                target_exam="CET-6",
                target_score=550,
                daily_time_budget_minutes=45,
            )
            profile_result = MagicMock()
            profile_result.scalar_one_or_none.return_value = profile_obj
            mock_session.execute = AsyncMock(return_value=profile_result)

            resp = await client.get(f"/api/learners/{learner_id}/profile")
            assert resp.status_code == 200
            data = resp.json()
            assert data["learner_id"] == learner_id
            assert data["target_exam"] == "CET-6"
            assert data["target_score"] == 550
            assert data["daily_time_budget_minutes"] == 45
