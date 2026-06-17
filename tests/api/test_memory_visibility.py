import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.learner import Learner
from src.models.runtime import AgentThread, ConversationMessage


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


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


class TestConversationList:
    @pytest.mark.asyncio
    async def test_list_conversations_returns_thread_summaries(self, client, mock_session):
        learner_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        thread = AgentThread(
            learner_id=learner_id,
            metadata_={
                "title": "四级阅读计划",
                "skill_id": "vocabulary_deposit",
                "skill_name": "词汇 Skill",
            },
        )
        thread.id = thread_id
        thread.created_at = now
        thread.updated_at = now
        user_message = ConversationMessage(
            learner_id=learner_id,
            thread_id=thread_id,
            role="user",
            content="我想练四级阅读",
            sequence=1,
        )
        user_message.id = uuid.uuid4()
        user_message.created_at = now
        assistant_message = ConversationMessage(
            learner_id=learner_id,
            thread_id=thread_id,
            role="assistant",
            content="我们先做一篇阅读。",
            sequence=2,
        )
        assistant_message.id = uuid.uuid4()
        assistant_message.created_at = now

        mock_session.execute = AsyncMock(
            side_effect=[
                _one(learner_id),
                _many([thread]),
                _many([user_message, assistant_message]),
            ]
        )

        response = await client.get(f"/api/learners/{learner_id}/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["thread_id"] == str(thread_id)
        assert data[0]["title"] == "四级阅读计划"
        assert data[0]["last_message"] == "我们先做一篇阅读。"
        assert data[0]["message_count"] == 2
        assert data[0]["skill_id"] == "vocabulary_deposit"
        assert data[0]["skill_name"] == "词汇 Skill"

    @pytest.mark.asyncio
    async def test_conversation_messages_use_sequence_when_timestamps_tie(
        self, client, mock_session
    ):
        learner_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        thread = AgentThread(learner_id=learner_id)
        thread.id = thread_id
        first = ConversationMessage(
            learner_id=learner_id,
            thread_id=thread_id,
            role="user",
            content="第一条",
            sequence=1,
        )
        first.id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        first.created_at = now
        second = ConversationMessage(
            learner_id=learner_id,
            thread_id=thread_id,
            role="assistant",
            content="第二条",
            sequence=2,
        )
        second.id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        second.created_at = now

        mock_session.execute = AsyncMock(
            side_effect=[
                _one(learner_id),
                _one(thread),
                _many([first, second]),
            ]
        )

        response = await client.get(
            f"/api/learners/{learner_id}/conversations/{thread_id}/messages"
        )

        assert response.status_code == 200
        data = response.json()
        assert [message["content"] for message in data] == ["第一条", "第二条"]
        assert [message["sequence"] for message in data] == [1, 2]

    @pytest.mark.asyncio
    async def test_exit_conversation_skill_clears_thread_metadata(self, client, mock_session):
        learner_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        thread = AgentThread(
            learner_id=learner_id,
            metadata_={"skill_id": "vocabulary_deposit", "skill_name": "词汇 Skill"},
        )
        thread.id = thread_id
        mock_session.execute = AsyncMock(
            side_effect=[
                _one(learner_id),
                _one(thread),
            ]
        )

        response = await client.delete(
            f"/api/learners/{learner_id}/conversations/{thread_id}/skill"
        )

        assert response.status_code == 204
        assert "skill_id" not in thread.metadata_
        assert "skill_name" not in thread.metadata_
        mock_session.flush.assert_awaited_once()


class TestMemorySummary:
    @pytest.mark.asyncio
    async def test_memory_summary_empty_state_uses_real_zeroes(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice", email="alice@example.com")
        learner.id = learner_id

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
            ]
        )

        response = await client.get(f"/api/learners/{learner_id}/memory/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["learner"]["nickname"] == "Alice"
        assert data["stats"]["conversation_count"] == 0
        assert data["stats"]["message_count"] == 0
        assert data["stats"]["total_vocab"] == 0
        assert data["skill_progress"] == {
            "grammar_learned": 0,
            "grammar_favorites": 0,
            "pronunciation_learned": 0,
            "pronunciation_opened": 0,
        }
        assert data["error_patterns"] == []
        assert data["recent_sessions"] == []

    @pytest.mark.asyncio
    async def test_memory_summary_includes_skill_progress_counts(self, client, mock_session):
        learner_id = uuid.uuid4()
        learner = Learner(nickname="Alice", email=None)
        learner.id = learner_id

        mock_session.execute = AsyncMock(
            side_effect=[
                _one(learner),
                _many([]),
                _count(0),
                _count(0),
                _count(0),
                _count(0),
                _count(3),
                _count(2),
                _count(5),
                _count(8),
                _many([]),
                _many([]),
            ]
        )

        response = await client.get(f"/api/learners/{learner_id}/memory/summary")

        assert response.status_code == 200
        assert response.json()["skill_progress"] == {
            "grammar_learned": 3,
            "grammar_favorites": 2,
            "pronunciation_learned": 5,
            "pronunciation_opened": 8,
        }
